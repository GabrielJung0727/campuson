"""공지사항 + 개발자 센터 API.

v0.3 엔드포인트
--------------
공지:
- GET    /announcements            — 활성 공지 조회 (대상별 필터)
- POST   /announcements            — 공지 등록 (ADMIN/DEV)
- PATCH  /announcements/{id}       — 수정 (ADMIN/DEV)
- DELETE /announcements/{id}       — 삭제 (ADMIN/DEV)

개발자 센터:
- GET    /dev/health-check         — LLM/RAG/DB/Redis 상태
- GET    /dev/stats                — 전체 시스템 통계
- PATCH  /users/{id}/role          — 사용자 역할/세부역할 변경
- GET    /dev/settings             — 현재 시스템 설정 조회
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.announcement import Announcement
from app.models.enums import (
    AdminRole,
    AnnouncementTarget,
    AnnouncementType,
    ProfessorRole,
    Role,
    StudentNationality,
)
from app.models.user import User
from app.schemas.common import MessageResponse

router = APIRouter(tags=["announcements"])


# === Schemas ===
class AnnouncementCreate(BaseModel):
    title: str = Field(..., max_length=200)
    content: str = Field(..., min_length=1)
    target_audience: AnnouncementTarget = AnnouncementTarget.ALL
    announcement_type: AnnouncementType = AnnouncementType.GENERAL
    ends_at: datetime | None = None
    send_email: bool = False


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    content: str
    target_audience: str
    announcement_type: str
    is_active: bool
    starts_at: str
    ends_at: str | None
    send_email: bool
    created_at: str


class RoleUpdateRequest(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    role: Role | None = None
    professor_role: ProfessorRole | None = None
    admin_role: AdminRole | None = None
    nationality: StudentNationality | None = None
    grade: int | None = Field(default=None, ge=1, le=4)

    # Track which fields were explicitly sent (including null)
    _provided_fields: set[str] = set()

    def __init__(self, **data: object) -> None:
        super().__init__(**data)
        object.__setattr__(self, '_provided_fields', set(data.keys()))


# === 공지사항 ===
@router.get("/announcements", summary="활성 공지 조회")
async def list_announcements(
    target: AnnouncementTarget | None = Query(default=None),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[AnnouncementResponse]:
    """현재 활성인 공지를 대상별로 필터링해서 반환."""
    now = datetime.now(UTC)
    filters = [
        Announcement.is_active.is_(True),
        Announcement.starts_at <= now,
    ]
    # 만료 안 됨
    filters.append(
        (Announcement.ends_at.is_(None)) | (Announcement.ends_at > now)
    )
    # 대상 필터: ADMIN/DEVELOPER는 전체 공지 열람 가능
    is_manager = current_user.role in (Role.ADMIN, Role.DEVELOPER)
    if target:
        filters.append(Announcement.target_audience == target)
    elif not is_manager:
        role_map = {
            Role.STUDENT: AnnouncementTarget.STUDENT,
            Role.PROFESSOR: AnnouncementTarget.PROFESSOR,
        }
        my_target = role_map.get(current_user.role, AnnouncementTarget.ALL)
        filters.append(
            Announcement.target_audience.in_([AnnouncementTarget.ALL, my_target])
        )

    stmt = (
        select(Announcement)
        .where(and_(*filters))
        .order_by(Announcement.created_at.desc())
        .limit(20)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    return [
        AnnouncementResponse(
            id=str(a.id), title=a.title, content=a.content,
            target_audience=a.target_audience.value,
            announcement_type=a.announcement_type.value,
            is_active=a.is_active, starts_at=a.starts_at.isoformat(),
            ends_at=a.ends_at.isoformat() if a.ends_at else None,
            send_email=a.send_email, created_at=a.created_at.isoformat(),
        )
        for a in rows
    ]


@router.post("/announcements", status_code=201, summary="공지 등록")
async def create_announcement(
    payload: AnnouncementCreate,
    current_user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> AnnouncementResponse:
    ann = Announcement(
        author_id=current_user.id,
        title=payload.title,
        content=payload.content,
        target_audience=payload.target_audience,
        announcement_type=payload.announcement_type,
        ends_at=payload.ends_at,
        send_email=payload.send_email,
    )
    db.add(ann)
    await db.flush()
    await db.refresh(ann)

    # 이메일 발송 (비동기, 실패 무시)
    if payload.send_email:
        try:
            from app.core.email import send_email as send_mail
            from app.core.email_templates import announcement_email

            html_body = announcement_email(
                title=payload.title,
                content=payload.content,
                announcement_type=payload.announcement_type.value,
                target_audience=payload.target_audience.value,
            )

            # 대상 사용자 조회
            target_filter = []
            if payload.target_audience != AnnouncementTarget.ALL:
                role_map = {
                    AnnouncementTarget.STUDENT: Role.STUDENT,
                    AnnouncementTarget.PROFESSOR: Role.PROFESSOR,
                    AnnouncementTarget.ADMIN: Role.ADMIN,
                    AnnouncementTarget.DEVELOPER: Role.DEVELOPER,
                }
                target_role = role_map.get(payload.target_audience)
                if target_role:
                    target_filter.append(User.role == target_role)

            users_stmt = select(User.email).where(User.status == "ACTIVE", *target_filter).limit(500)
            emails = [r[0] for r in (await db.execute(users_stmt)).all()]

            # 유형별 제목 프리픽스
            _prefix = {
                AnnouncementType.URGENT: "[긴급]",
                AnnouncementType.MAINTENANCE: "[점검]",
            }
            subject_prefix = _prefix.get(payload.announcement_type, "")
            subject = f"[CampusON] {subject_prefix} {payload.title}".replace("  ", " ")

            for email in emails[:100]:
                await send_mail(email, subject, html_body)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Announcement email failed (non-blocking)")

    return AnnouncementResponse(
        id=str(ann.id), title=ann.title, content=ann.content,
        target_audience=ann.target_audience.value,
        announcement_type=ann.announcement_type.value,
        is_active=ann.is_active, starts_at=ann.starts_at.isoformat(),
        ends_at=ann.ends_at.isoformat() if ann.ends_at else None,
        send_email=ann.send_email, created_at=ann.created_at.isoformat(),
    )


@router.delete("/announcements/{ann_id}", summary="공지 삭제")
async def delete_announcement(
    ann_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    ann = await db.get(Announcement, ann_id)
    if ann is None:
        raise HTTPException(status_code=404, detail="Not found")
    await db.delete(ann)
    await db.flush()
    return MessageResponse(message="Deleted")


# === 사용자 역할 변경 ===
@router.patch("/users/{user_id}/role", summary="사용자 역할/세부역할 변경")
async def update_user_role(
    user_id: uuid.UUID,
    payload: RoleUpdateRequest,
    _admin: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    provided = object.__getattribute__(payload, '_provided_fields')
    if 'role' in provided:
        user.role = payload.role
    if 'professor_role' in provided:
        user.professor_role = payload.professor_role
    if 'admin_role' in provided:
        user.admin_role = payload.admin_role
    if 'nationality' in provided:
        user.nationality = payload.nationality
    if 'grade' in provided:
        user.grade = payload.grade

    await db.flush()
    return {
        "id": str(user.id), "name": user.name, "role": user.role.value,
        "professor_role": user.professor_role.value if user.professor_role else None,
        "admin_role": user.admin_role.value if user.admin_role else None,
        "nationality": user.nationality.value if user.nationality else None,
        "grade": user.grade,
    }


# === 개발자 센터 ===
@router.get("/dev/health-check", summary="시스템 상태 체크")
async def dev_health_check(
    _dev: User = Depends(require_roles(Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """DB, Redis, LLM, Embedding 상태를 한 번에 확인."""
    from sqlalchemy import text
    from app.core.redis import get_redis_client

    results = {}

    # DB
    try:
        await db.execute(text("SELECT 1"))
        results["db"] = "ok"
    except Exception as e:
        results["db"] = f"error: {e}"

    # Redis
    try:
        r = get_redis_client()
        await r.ping()
        results["redis"] = "ok"
    except Exception as e:
        results["redis"] = f"error: {e}"

    # LLM
    from app.core.llm import get_llm_gateway
    gw = get_llm_gateway()
    results["llm"] = {"provider": gw.provider_name.value, "model": gw.model}

    # Embedding
    from app.core.embeddings import get_embedding_gateway
    egw = get_embedding_gateway()
    results["embedding"] = {"provider": egw.provider_name.value, "model": egw.model, "dimensions": egw.dimensions}

    # SMTP
    results["smtp"] = {"enabled": settings.smtp_enabled, "host": settings.smtp_host}

    return results


@router.get("/dev/stats", summary="전체 시스템 통계")
async def dev_stats(
    _dev: User = Depends(require_roles(Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """테이블별 row 수, 학과별 사용자 수, AI 호출 통계."""
    from app.models.ai_request_log import AIRequestLog
    from app.models.learning_history import LearningHistory
    from app.models.question import Question
    from app.models.kb_document import KBDocument, KBChunk

    tables = {
        "users": User,
        "questions": Question,
        "learning_history": LearningHistory,
        "ai_request_logs": AIRequestLog,
        "kb_documents": KBDocument,
        "kb_chunks": KBChunk,
        "announcements": Announcement,
    }
    counts = {}
    for name, model in tables.items():
        count = (await db.execute(select(func.count(model.id)))).scalar_one()
        counts[name] = count

    # 학과별 사용자
    dept_stmt = (
        select(User.department, User.role, func.count(User.id))
        .group_by(User.department, User.role)
    )
    dept_rows = (await db.execute(dept_stmt)).all()
    dept_stats = [{"department": r[0].value, "role": r[1].value, "count": int(r[2])} for r in dept_rows]

    return {"table_counts": counts, "department_stats": dept_stats}


@router.get("/dev/settings", summary="현재 시스템 설정 조회")
async def dev_settings(
    _dev: User = Depends(require_roles(Role.DEVELOPER)),
) -> dict:
    """현재 활성화된 시스템 설정 (민감 값 마스킹)."""
    def mask(val: str) -> str:
        if not val or len(val) < 4:
            return "***"
        return val[:3] + "***" + val[-2:]

    return {
        "env": settings.env,
        "debug": settings.debug,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "llm_temperature": settings.llm_temperature,
        "llm_max_tokens": settings.llm_max_tokens,
        "anthropic_api_key": mask(settings.anthropic_api_key) if settings.anthropic_api_key else "(empty)",
        "openai_api_key": mask(settings.openai_api_key) if settings.openai_api_key else "(empty)",
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimensions": settings.embedding_dimensions,
        "smtp_enabled": settings.smtp_enabled,
        "smtp_host": settings.smtp_host,
        "smtp_user": mask(settings.smtp_user) if settings.smtp_user else "(empty)",
        "audit_log_enabled": settings.audit_log_enabled,
        "bcrypt_rounds": settings.bcrypt_rounds,
        "jwt_access_token_expire_minutes": settings.jwt_access_token_expire_minutes,
        "cors_origins": settings.cors_origins,
    }
