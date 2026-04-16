"""캘린더 + 교수 코멘트 라우터 (v0.8).

엔드포인트
---------
- POST   /calendar/events            — 일정 생성
- GET    /calendar/events            — 일정 조회
- PATCH  /calendar/events/{id}       — 일정 수정
- DELETE /calendar/events/{id}       — 일정 삭제
- POST   /calendar/sync-assignments  — 과제 마감 자동 동기화
- POST   /comments                   — 교수 코멘트 생성
- GET    /comments/student/{id}      — 학생 코멘트 목록
- GET    /comments/target/{type}/{id}— 대상별 코멘트 목록
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services import calendar_service

router = APIRouter(tags=["calendar"])


# === Schemas ===


class EventCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    event_type: str = Field(
        "custom",
        pattern="^(assignment_due|exam|practicum|diagnostic|review|custom)$",
    )
    start_at: datetime
    end_at: datetime | None = None
    all_day: bool = False
    description: str | None = None
    reference_type: str | None = None
    reference_id: uuid.UUID | None = None
    color: str | None = None
    reminder_minutes: int | None = None


class EventUpdateRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    all_day: bool | None = None
    color: str | None = None
    reminder_minutes: int | None = None
    is_completed: bool | None = None


class CommentCreateRequest(BaseModel):
    student_id: uuid.UUID
    target_type: str = Field(
        ...,
        pattern="^(learning_history|assignment_submission|practicum_session|general)$",
    )
    content: str = Field(..., min_length=1, max_length=2000)
    target_id: uuid.UUID | None = None
    is_private: bool = False


# === Calendar Endpoints ===


@router.post("/calendar/events", status_code=status.HTTP_201_CREATED)
async def create_event(
    body: EventCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """일정 생성."""
    event = await calendar_service.create_event(
        db, user.id,
        title=body.title,
        event_type=body.event_type,
        start_at=body.start_at,
        end_at=body.end_at,
        all_day=body.all_day,
        description=body.description,
        reference_type=body.reference_type,
        reference_id=body.reference_id,
        color=body.color,
        reminder_minutes=body.reminder_minutes,
        school_id=user.school_id,
    )
    await db.commit()
    return {"id": str(event.id), "title": event.title}


@router.get("/calendar/events")
async def get_events(
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    event_type: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """일정 조회 (기간/유형 필터)."""
    return await calendar_service.get_events(
        db, user.id, start=start, end=end, event_type=event_type,
    )


@router.patch("/calendar/events/{event_id}")
async def update_event(
    event_id: uuid.UUID,
    body: EventUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """일정 수정."""
    event = await calendar_service.update_event(
        db, event_id, user.id, **body.model_dump(exclude_none=True),
    )
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.commit()
    return {"id": str(event.id), "title": event.title}


@router.delete("/calendar/events/{event_id}")
async def delete_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """일정 삭제."""
    ok = await calendar_service.delete_event(db, event_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Event not found")
    await db.commit()
    return {"deleted": True}


@router.post("/calendar/sync-assignments")
async def sync_assignment_deadlines(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """과제 마감일을 캘린더에 자동 동기화."""
    count = await calendar_service.sync_assignment_deadlines(db, user.id)
    await db.commit()
    return {"synced": count}


# === Professor Comment Endpoints ===


@router.post("/comments", status_code=status.HTTP_201_CREATED)
async def create_comment(
    body: CommentCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
):
    """교수 코멘트 생성."""
    comment = await calendar_service.create_comment(
        db, user.id, body.student_id,
        target_type=body.target_type,
        content=body.content,
        target_id=body.target_id,
        is_private=body.is_private,
    )
    await db.commit()
    return {"id": str(comment.id)}


@router.get("/comments/student/{student_id}")
async def get_student_comments(
    student_id: uuid.UUID,
    include_private: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """학생의 코멘트 목록.

    학생 본인은 is_private=False만 조회 가능.
    교수 이상은 include_private=True 가능.
    """
    if user.role == Role.STUDENT:
        include_private = False
    return await calendar_service.get_comments_for_student(
        db, student_id, include_private=include_private,
    )


@router.get("/comments/target/{target_type}/{target_id}")
async def get_target_comments(
    target_type: str,
    target_id: uuid.UUID,
    include_private: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
):
    """대상별 코멘트 목록."""
    if user.role == Role.STUDENT:
        include_private = False
    return await calendar_service.get_comments_for_target(
        db, target_type, target_id, include_private=include_private,
    )
