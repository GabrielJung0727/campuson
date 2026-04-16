"""알림 API (v0.6)."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import NotificationCategory
from app.models.user import User
from app.services.notification_service import (
    delete_notification,
    get_notifications,
    mark_all_as_read,
    mark_as_read,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    category: str
    title: str
    message: str
    link: str | None
    is_read: bool
    email_sent: bool
    push_sent: bool
    created_at: datetime


@router.get("")
async def list_notifications(
    unread_only: bool = False,
    category: NotificationCategory | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 알림 목록."""
    items, total, unread_count = await get_notifications(
        db, user.id,
        unread_only=unread_only, category=category,
        page=page, page_size=page_size,
    )
    return {
        "items": [
            NotificationResponse(
                id=n.id,
                category=n.category.value,
                title=n.title,
                message=n.message,
                link=n.link,
                is_read=n.is_read,
                email_sent=n.email_sent,
                push_sent=n.push_sent,
                created_at=n.created_at,
            )
            for n in items
        ],
        "total": total,
        "unread_count": unread_count,
        "page": page,
        "page_size": page_size,
    }


@router.get("/unread-count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """읽지 않은 알림 수."""
    _, _, count = await get_notifications(db, user.id, page_size=0)
    return {"unread_count": count}


@router.put("/{notification_id}/read")
async def read_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """알림 읽음 처리."""
    ok = await mark_as_read(db, user.id, notification_id)
    if not ok:
        raise HTTPException(404, "알림을 찾을 수 없습니다")
    return {"success": True}


@router.put("/read-all")
async def read_all_notifications(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """모든 알림 읽음 처리."""
    count = await mark_all_as_read(db, user.id)
    return {"marked_read": count}


@router.delete("/{notification_id}")
async def remove_notification(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """알림 삭제."""
    ok = await delete_notification(db, user.id, notification_id)
    if not ok:
        raise HTTPException(404, "알림을 찾을 수 없습니다")
    return {"success": True}
