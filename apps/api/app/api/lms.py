"""LMS 연동 라우터 (v0.8).

엔드포인트
---------
- POST   /lms/sso/initiate           — SSO 인증 시작
- POST   /lms/sso/callback           — SSO 콜백 처리
- GET    /lms/lti13/login             — LTI 1.3 로그인 URL
- POST   /lms/courses                 — LMS 과목 매핑 생성
- GET    /lms/courses                 — LMS 과목 목록
- POST   /lms/grades/sync             — 성적 동기화
- GET    /lms/grades/history/{id}     — 성적 동기화 이력
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services import lms_service, school_service

router = APIRouter(prefix="/lms", tags=["lms"])


# === Schemas ===


class SSOCallbackRequest(BaseModel):
    external_id: str
    email: str
    name: str
    attributes: dict | None = None


class LMSCourseCreateRequest(BaseModel):
    class_id: uuid.UUID
    lms_course_id: str
    lms_course_name: str | None = None
    lms_platform: str = "lti13"
    sync_grades: bool = False
    grade_column_id: str | None = None


class GradeSyncRequest(BaseModel):
    lms_course_id: uuid.UUID
    student_id: uuid.UUID
    score: float
    score_type: str = Field(..., pattern="^(quiz|assignment|diagnostic|practicum)$")
    source_id: str | None = None


# === Endpoints ===


@router.post("/sso/initiate")
async def initiate_sso(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """SSO 인증 시작 — IdP 리다이렉트 URL 반환."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="User not associated with a school")
    return await lms_service.initiate_sso(db, user.school_id)


@router.post("/sso/callback")
async def sso_callback(
    body: SSOCallbackRequest,
    school_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """SSO 콜백 처리 (외부 IdP → 내부 사용자 매칭)."""
    result = await lms_service.process_sso_callback(
        db, school_id, **body.model_dump(),
    )
    await db.commit()
    return result


@router.get("/lti13/login")
async def lti13_login(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """LTI 1.3 OIDC 로그인 초기화 URL."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="User not associated with a school")
    settings = await school_service.get_school_settings(db, user.school_id)
    if not settings:
        raise HTTPException(status_code=404, detail="School settings not found")
    return lms_service.build_lti13_login_url(settings)


@router.post("/courses", status_code=status.HTTP_201_CREATED)
async def create_lms_course(
    body: LMSCourseCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
):
    """LMS 과목 매핑 생성."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="User not associated with a school")
    course = await lms_service.create_lms_course(
        db, user.school_id, body.class_id, **body.model_dump(exclude={"class_id"}),
    )
    await db.commit()
    return {"id": str(course.id), "lms_course_id": course.lms_course_id}


@router.get("/courses")
async def list_lms_courses(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """학교의 LMS 연동 과목 목록."""
    if not user.school_id:
        raise HTTPException(status_code=400, detail="User not associated with a school")
    return await lms_service.get_lms_courses(db, user.school_id)


@router.post("/grades/sync")
async def sync_grade(
    body: GradeSyncRequest,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """성적 LMS 동기화."""
    sync = await lms_service.sync_grade(
        db, body.lms_course_id, body.student_id,
        score=body.score,
        score_type=body.score_type,
        source_id=body.source_id,
    )
    await db.commit()
    return {"id": str(sync.id), "success": sync.success}


@router.get("/grades/history/{lms_course_id}")
async def get_grade_history(
    lms_course_id: uuid.UUID,
    student_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """성적 동기화 이력."""
    return await lms_service.get_grade_sync_history(
        db, lms_course_id, student_id=student_id, limit=limit,
    )
