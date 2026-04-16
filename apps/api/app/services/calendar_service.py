"""캘린더 + 교수 코멘트 서비스 (v0.8).

- 일정 CRUD
- 과제 마감 자동 연동
- 교수 피드백 코멘트
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar import CalendarEvent, ProfessorComment
from app.models.assignment import Assignment

logger = logging.getLogger(__name__)


# === Calendar Events ===


async def create_event(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    title: str,
    event_type: str,
    start_at: datetime,
    end_at: datetime | None = None,
    all_day: bool = False,
    description: str | None = None,
    reference_type: str | None = None,
    reference_id: uuid.UUID | None = None,
    color: str | None = None,
    reminder_minutes: int | None = None,
    school_id: uuid.UUID | None = None,
) -> CalendarEvent:
    """일정 생성."""
    event = CalendarEvent(
        user_id=user_id,
        school_id=school_id,
        title=title,
        description=description,
        event_type=event_type,
        start_at=start_at,
        end_at=end_at,
        all_day=all_day,
        reference_type=reference_type,
        reference_id=reference_id,
        color=color,
        reminder_minutes=reminder_minutes,
    )
    db.add(event)
    await db.flush()
    return event


async def get_events(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    event_type: str | None = None,
) -> list[dict]:
    """사용자 일정 조회."""
    now = datetime.now(timezone.utc)
    if not start:
        start = now - timedelta(days=30)
    if not end:
        end = now + timedelta(days=90)

    stmt = (
        select(CalendarEvent)
        .where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.start_at >= start,
            CalendarEvent.start_at <= end,
        )
        .order_by(CalendarEvent.start_at)
    )
    if event_type:
        stmt = stmt.where(CalendarEvent.event_type == event_type)

    rows = list((await db.execute(stmt)).scalars().all())
    return [_event_to_dict(e) for e in rows]


async def update_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
    **kwargs,
) -> CalendarEvent | None:
    """일정 수정."""
    event = await db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user_id,
        )
    )
    if not event:
        return None
    for k, v in kwargs.items():
        if hasattr(event, k) and v is not None:
            setattr(event, k, v)
    await db.flush()
    return event


async def delete_event(
    db: AsyncSession,
    event_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """일정 삭제."""
    event = await db.scalar(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user_id,
        )
    )
    if not event:
        return False
    await db.delete(event)
    await db.flush()
    return True


async def sync_assignment_deadlines(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """과제 마감일을 캘린더에 자동 동기화."""
    # 미래 마감 과제만
    stmt = select(Assignment).where(
        Assignment.status == "PUBLISHED",
        Assignment.due_date >= datetime.now(timezone.utc),
    )
    assignments = list((await db.execute(stmt)).scalars().all())

    synced = 0
    for a in assignments:
        # 이미 등록된 이벤트 확인
        existing = await db.scalar(
            select(CalendarEvent).where(
                CalendarEvent.user_id == user_id,
                CalendarEvent.reference_type == "assignment",
                CalendarEvent.reference_id == a.id,
            )
        )
        if not existing and a.due_date:
            await create_event(
                db, user_id,
                title=f"과제 마감: {a.title}",
                event_type="assignment_due",
                start_at=a.due_date,
                all_day=False,
                reference_type="assignment",
                reference_id=a.id,
                color="#F59E0B",
                reminder_minutes=60,
            )
            synced += 1

    return synced


def _event_to_dict(e: CalendarEvent) -> dict:
    return {
        "id": str(e.id),
        "title": e.title,
        "description": e.description,
        "event_type": e.event_type,
        "start_at": e.start_at.isoformat(),
        "end_at": e.end_at.isoformat() if e.end_at else None,
        "all_day": e.all_day,
        "reference_type": e.reference_type,
        "reference_id": str(e.reference_id) if e.reference_id else None,
        "color": e.color,
        "reminder_minutes": e.reminder_minutes,
        "is_completed": e.is_completed,
    }


# === Professor Comments ===


async def create_comment(
    db: AsyncSession,
    professor_id: uuid.UUID,
    student_id: uuid.UUID,
    *,
    target_type: str,
    content: str,
    target_id: uuid.UUID | None = None,
    is_private: bool = False,
) -> ProfessorComment:
    """교수 코멘트 생성."""
    comment = ProfessorComment(
        professor_id=professor_id,
        student_id=student_id,
        target_type=target_type,
        target_id=target_id,
        content=content,
        is_private=is_private,
    )
    db.add(comment)
    await db.flush()
    return comment


async def get_comments_for_student(
    db: AsyncSession,
    student_id: uuid.UUID,
    *,
    include_private: bool = False,
) -> list[dict]:
    """학생에 대한 코멘트 목록."""
    stmt = (
        select(ProfessorComment)
        .where(ProfessorComment.student_id == student_id)
        .order_by(ProfessorComment.created_at.desc())
    )
    if not include_private:
        stmt = stmt.where(ProfessorComment.is_private.is_(False))

    rows = list((await db.execute(stmt)).scalars().all())
    return [_comment_to_dict(c) for c in rows]


async def get_comments_for_target(
    db: AsyncSession,
    target_type: str,
    target_id: uuid.UUID,
    *,
    include_private: bool = False,
) -> list[dict]:
    """특정 대상에 대한 코멘트 목록."""
    stmt = (
        select(ProfessorComment)
        .where(
            ProfessorComment.target_type == target_type,
            ProfessorComment.target_id == target_id,
        )
        .order_by(ProfessorComment.created_at.desc())
    )
    if not include_private:
        stmt = stmt.where(ProfessorComment.is_private.is_(False))

    rows = list((await db.execute(stmt)).scalars().all())
    return [_comment_to_dict(c) for c in rows]


def _comment_to_dict(c: ProfessorComment) -> dict:
    return {
        "id": str(c.id),
        "professor_id": str(c.professor_id),
        "student_id": str(c.student_id),
        "target_type": c.target_type,
        "target_id": str(c.target_id) if c.target_id else None,
        "content": c.content,
        "is_private": c.is_private,
        "created_at": c.created_at.isoformat(),
    }
