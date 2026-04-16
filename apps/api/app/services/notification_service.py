"""알림 서비스 (v0.6).

인앱 알림 + 이메일 발송 + 웹 푸시 지원:
- 과제 마감 임박
- 진단 테스트 미완료 리마인더
- 교수 피드백 도착
- 취약 영역 복습 추천
- 실습 시험 일정
- 공지사항 알림
- 지식베이스 업데이트 반영
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import NotificationCategory, Role
from app.models.notification import Notification
from app.models.user import User

logger = logging.getLogger(__name__)


# === 알림 생성 ===


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    category: NotificationCategory,
    title: str,
    message: str,
    link: str | None = None,
    extra_data: dict | None = None,
    send_email: bool = False,
    send_push: bool = False,
) -> Notification:
    """인앱 알림 생성 + 선택적 이메일/푸시 발송."""
    notif = Notification(
        user_id=user_id,
        category=category,
        title=title,
        message=message,
        link=link,
        extra_data=extra_data,
    )
    db.add(notif)

    # 이메일 발송 (비동기 — BackgroundJob으로 위임)
    if send_email:
        from app.services.task_queue import enqueue_job
        from app.models.enums import JobType

        user = await db.get(User, user_id)
        if user and user.email:
            await enqueue_job(
                db, JobType.EMAIL_SEND,
                params={"to": user.email, "subject": title, "body": message},
            )
            notif.email_sent = True

    # 웹 푸시 발송 (향후 FCM/Web Push API 연동)
    if send_push:
        notif.push_sent = True
        # TODO: FCM/Web Push API 연동

    await db.flush()
    await db.refresh(notif)
    return notif


async def create_bulk_notifications(
    db: AsyncSession,
    *,
    user_ids: list[uuid.UUID],
    category: NotificationCategory,
    title: str,
    message: str,
    link: str | None = None,
    send_email: bool = False,
) -> int:
    """여러 사용자에게 동일 알림 일괄 생성."""
    count = 0
    for uid in user_ids:
        await create_notification(
            db, user_id=uid, category=category,
            title=title, message=message, link=link,
            send_email=send_email,
        )
        count += 1
    await db.flush()
    return count


# === 알림 조회 ===


async def get_notifications(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    unread_only: bool = False,
    category: NotificationCategory | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Notification], int, int]:
    """사용자 알림 목록 + 읽지 않은 수."""
    base = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        base = base.where(Notification.is_read.is_(False))
    if category:
        base = base.where(Notification.category == category)

    total = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    unread_count = (await db.execute(
        select(func.count()).where(
            Notification.user_id == user_id,
            Notification.is_read.is_(False),
        )
    )).scalar_one()

    items = list(
        (await db.execute(
            base.order_by(desc(Notification.created_at))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )).scalars().all()
    )

    return items, total, unread_count


async def mark_as_read(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID,
) -> bool:
    """단일 알림 읽음 처리."""
    result = await db.execute(
        update(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return result.rowcount > 0


async def mark_all_as_read(db: AsyncSession, user_id: uuid.UUID) -> int:
    """모든 알림 읽음 처리."""
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(timezone.utc))
    )
    await db.flush()
    return result.rowcount


async def delete_notification(
    db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID,
) -> bool:
    """알림 삭제."""
    result = await db.execute(
        delete(Notification)
        .where(Notification.id == notification_id, Notification.user_id == user_id)
    )
    await db.flush()
    return result.rowcount > 0


# === 트리거 알림 ===


async def notify_assignment_due(
    db: AsyncSession, assignment_id: uuid.UUID,
    student_ids: list[uuid.UUID], title: str, due_date: datetime,
) -> int:
    """과제 마감 임박 알림."""
    hours_left = max(0, (due_date - datetime.now(timezone.utc)).total_seconds() / 3600)
    message = f"과제 '{title}'의 마감이 {int(hours_left)}시간 남았습니다."

    return await create_bulk_notifications(
        db, user_ids=student_ids,
        category=NotificationCategory.ASSIGNMENT_DUE,
        title="📝 과제 마감 임박",
        message=message,
        link=f"/quiz?assignment={assignment_id}",
        send_email=hours_left < 24,
    )


async def notify_diagnostic_reminder(
    db: AsyncSession, user_id: uuid.UUID,
) -> Notification:
    """진단 테스트 미완료 리마인더."""
    return await create_notification(
        db, user_id=user_id,
        category=NotificationCategory.DIAGNOSTIC_REMINDER,
        title="🧪 진단 테스트를 완료해 주세요",
        message="맞춤 학습을 위해 진단 테스트를 먼저 완료해 주세요. 약 15분 소요됩니다.",
        link="/diagnostic",
        send_email=True,
    )


async def notify_professor_feedback(
    db: AsyncSession, student_id: uuid.UUID,
    professor_name: str, context: str,
) -> Notification:
    """교수 피드백 도착 알림."""
    return await create_notification(
        db, user_id=student_id,
        category=NotificationCategory.PROFESSOR_FEEDBACK,
        title="💬 교수님 피드백이 도착했습니다",
        message=f"{professor_name} 교수님이 {context}에 대한 피드백을 남겼습니다.",
        link="/dashboard",
    )


async def notify_weak_area_review(
    db: AsyncSession, user_id: uuid.UUID, weak_areas: list[str],
) -> Notification:
    """취약 영역 복습 추천 알림."""
    areas_str = ", ".join(weak_areas[:3])
    return await create_notification(
        db, user_id=user_id,
        category=NotificationCategory.WEAK_AREA_REVIEW,
        title="📚 복습 추천",
        message=f"취약 영역({areas_str})에 대한 복습 문제가 준비되었습니다.",
        link="/quiz",
    )


async def notify_practicum_schedule(
    db: AsyncSession, student_ids: list[uuid.UUID],
    practicum_name: str, scheduled_at: datetime,
) -> int:
    """실습 시험 일정 알림."""
    date_str = scheduled_at.strftime("%m/%d %H:%M")
    return await create_bulk_notifications(
        db, user_ids=student_ids,
        category=NotificationCategory.PRACTICUM_SCHEDULE,
        title="🏥 실습 시험 일정 안내",
        message=f"'{practicum_name}' 실습 시험이 {date_str}에 예정되어 있습니다.",
        link="/practicum",
        send_email=True,
    )


async def notify_announcement(
    db: AsyncSession, user_ids: list[uuid.UUID],
    announcement_title: str,
) -> int:
    """공지사항 알림."""
    return await create_bulk_notifications(
        db, user_ids=user_ids,
        category=NotificationCategory.ANNOUNCEMENT,
        title="📢 새 공지사항",
        message=f"'{announcement_title}' 공지가 등록되었습니다.",
        link="/dashboard",
    )


async def notify_kb_update(
    db: AsyncSession, department_user_ids: list[uuid.UUID],
    document_title: str,
) -> int:
    """지식베이스 업데이트 알림."""
    return await create_bulk_notifications(
        db, user_ids=department_user_ids,
        category=NotificationCategory.KB_UPDATE,
        title="📖 학습 자료 업데이트",
        message=f"'{document_title}' 자료가 업데이트되었습니다.",
        link="/chat",
    )
