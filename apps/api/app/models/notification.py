"""Notification 모델 — 인앱 알림 시스템 (v0.6).

사용자별 알림을 저장하고, 읽음 상태를 추적한다.
이메일/웹 푸시 발송 여부도 기록한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import NotificationCategory


class Notification(Base, UUIDPrimaryKeyMixin):
    """인앱 알림."""

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- 내용 ---
    category: Mapped[NotificationCategory] = mapped_column(
        SAEnum(
            NotificationCategory,
            name="notification_category_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="클릭 시 이동 경로")
    extra_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # --- 상태 ---
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- 발송 채널 ---
    email_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    push_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_notifications_user_read", "user_id", "is_read"),
        Index("ix_notifications_user_created", "user_id", "created_at"),
        Index("ix_notifications_category", "category"),
    )
