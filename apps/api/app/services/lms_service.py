"""LMS 연동 서비스 (v0.8).

- LTI 1.3 연동 규격
- SSO (SAML/OIDC) 인증 흐름
- 성적 데이터 동기화
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lms import LMSCourse, LMSGradeSync, SSOSession
from app.models.school import SchoolSettings
from app.models.user import User

logger = logging.getLogger(__name__)


# === LTI 1.3 ===


def build_lti13_login_url(school_settings: dict) -> dict:
    """LTI 1.3 OIDC 로그인 초기화 URL 생성.

    LTI 1.3 흐름:
    1. Platform → Tool: OIDC initiation (login_hint, target_link_uri)
    2. Tool → Platform: Authorization request
    3. Platform → Tool: id_token (JWT) with LTI claims
    """
    lms_config = school_settings.get("lms_config") or {}
    return {
        "auth_url": lms_config.get("auth_url", ""),
        "token_url": lms_config.get("token_url", ""),
        "client_id": lms_config.get("client_id", ""),
        "redirect_uri": lms_config.get("redirect_uri", ""),
        "response_type": "id_token",
        "scope": "openid",
        "response_mode": "form_post",
        "prompt": "none",
    }


def validate_lti13_token(id_token: str, lms_config: dict) -> dict | None:
    """LTI 1.3 id_token 검증 (JWK 기반).

    실제 운영에서는 PyJWT + jwcrypto로 검증.
    여기서는 인터페이스만 ��의.
    """
    # TODO: PyJWT + jwcrypto로 JWK 기반 검증 구현
    # 1. Platform의 JWKS URL에서 공개키 fetch
    # 2. id_token의 header에서 kid 추출
    # 3. 해당 공개키로 서명 검증
    # 4. iss, aud, exp 등 클레임 검증
    logger.info("LTI 1.3 token validation requested (implementation pending)")
    return None


# === SSO ===


async def initiate_sso(
    db: AsyncSession,
    school_id: uuid.UUID,
) -> dict:
    """SSO 인증 시작 — 외부 IdP 리다이렉트 URL 생성."""
    settings = await db.scalar(
        select(SchoolSettings).where(SchoolSettings.school_id == school_id)
    )
    if not settings or not settings.sso_enabled:
        return {"error": "SSO not enabled for this school"}

    sso_config = settings.sso_config or {}

    if settings.sso_provider == "saml":
        return {
            "redirect_url": sso_config.get("login_url", ""),
            "provider": "saml",
            "entity_id": sso_config.get("entity_id", ""),
        }
    elif settings.sso_provider == "oidc":
        return {
            "redirect_url": sso_config.get("authorization_endpoint", ""),
            "provider": "oidc",
            "client_id": sso_config.get("client_id", ""),
            "scope": "openid profile email",
        }
    else:
        return {"error": f"Unsupported SSO provider: {settings.sso_provider}"}


async def process_sso_callback(
    db: AsyncSession,
    school_id: uuid.UUID,
    *,
    external_id: str,
    email: str,
    name: str,
    attributes: dict | None = None,
) -> dict:
    """SSO 콜백 처리 — 사용자 매칭 또는 자동 생성.

    1. external_id로 기존 SSO 세션 확인
    2. 없으면 email로 기존 사용자 매칭
    3. 그래도 없으면 사용자 자동 생성 (JIT provisioning)
    """
    # 기존 SSO 세션에서 사용자 찾기
    existing_sso = await db.scalar(
        select(SSOSession).where(
            SSOSession.school_id == school_id,
            SSOSession.external_id == external_id,
        )
    )

    if existing_sso:
        user = await db.get(User, existing_sso.user_id)
        if user:
            return {"user_id": str(user.id), "email": user.email, "action": "existing_sso"}

    # email로 기존 사용자 매칭
    user = await db.scalar(
        select(User).where(User.email == email, User.school_id == school_id)
    )

    if not user:
        # JIT provisioning — 학교 도메인 확인 후 자동 생성은
        # 실제로는 관리자 승인이 필요할 수 있음
        return {
            "action": "user_not_found",
            "email": email,
            "external_id": external_id,
            "message": "User not found. Manual registration or auto-provisioning required.",
        }

    # SSO 세션 생성
    sso_session = SSOSession(
        school_id=school_id,
        user_id=user.id,
        sso_provider="sso",
        external_id=external_id,
        session_data=attributes,
    )
    db.add(sso_session)
    await db.flush()

    return {"user_id": str(user.id), "email": user.email, "action": "matched_by_email"}


# === Grade Sync ===


async def create_lms_course(
    db: AsyncSession,
    school_id: uuid.UUID,
    class_id: uuid.UUID,
    *,
    lms_course_id: str,
    lms_course_name: str | None = None,
    lms_platform: str = "lti13",
    sync_grades: bool = False,
    grade_column_id: str | None = None,
) -> LMSCourse:
    """LMS 과목 매핑 생성."""
    course = LMSCourse(
        school_id=school_id,
        class_id=class_id,
        lms_course_id=lms_course_id,
        lms_course_name=lms_course_name,
        lms_platform=lms_platform,
        sync_grades=sync_grades,
        grade_column_id=grade_column_id,
    )
    db.add(course)
    await db.flush()
    return course


async def sync_grade(
    db: AsyncSession,
    lms_course_id: uuid.UUID,
    student_id: uuid.UUID,
    *,
    score: float,
    score_type: str,
    source_id: str | None = None,
) -> LMSGradeSync:
    """성적을 LMS로 동기화.

    실제 LMS API 호출은 학교 설정의 lms_config에서 token_url,
    grade_service_url 등을 참조하여 수행.
    여기서는 기록만 저장.
    """
    # TODO: 실제 LMS API 호출 (AGS - Assignment and Grade Services)
    # 1. access_token 획득 (client_credentials grant)
    # 2. score endpoint로 POST
    # 3. 응답 저장

    sync = LMSGradeSync(
        lms_course_id=lms_course_id,
        student_id=student_id,
        score=score,
        score_type=score_type,
        source_id=source_id,
        success=True,  # 실제 구현 시 API 호출 결과 반영
    )
    db.add(sync)
    await db.flush()

    # LMS Course last_synced_at 업데이트
    course = await db.get(LMSCourse, lms_course_id)
    if course:
        course.last_synced_at = datetime.now(timezone.utc)
        await db.flush()

    return sync


async def get_grade_sync_history(
    db: AsyncSession,
    lms_course_id: uuid.UUID,
    *,
    student_id: uuid.UUID | None = None,
    limit: int = 50,
) -> list[dict]:
    """성적 동기화 이력 조회."""
    stmt = (
        select(LMSGradeSync)
        .where(LMSGradeSync.lms_course_id == lms_course_id)
        .order_by(LMSGradeSync.synced_at.desc())
        .limit(limit)
    )
    if student_id:
        stmt = stmt.where(LMSGradeSync.student_id == student_id)

    rows = list((await db.execute(stmt)).scalars().all())
    return [
        {
            "id": str(r.id),
            "student_id": str(r.student_id),
            "score": r.score,
            "score_type": r.score_type,
            "source_id": r.source_id,
            "success": r.success,
            "error_message": r.error_message,
            "synced_at": r.synced_at.isoformat(),
        }
        for r in rows
    ]


async def get_lms_courses(
    db: AsyncSession, school_id: uuid.UUID,
) -> list[dict]:
    """학교의 LMS 연동 과목 목록."""
    rows = list((await db.execute(
        select(LMSCourse)
        .where(LMSCourse.school_id == school_id)
        .order_by(LMSCourse.created_at.desc())
    )).scalars().all())

    return [
        {
            "id": str(r.id),
            "class_id": str(r.class_id),
            "lms_course_id": r.lms_course_id,
            "lms_course_name": r.lms_course_name,
            "lms_platform": r.lms_platform,
            "sync_grades": r.sync_grades,
            "last_synced_at": r.last_synced_at.isoformat() if r.last_synced_at else None,
        }
        for r in rows
    ]
