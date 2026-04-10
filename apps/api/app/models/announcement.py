"""공지사항 모델 — v0.3."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import AnnouncementTarget, AnnouncementType


class Announcement(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """공지사항."""

    __tablename__ = "announcements"

    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    target_audience: Mapped[AnnouncementTarget] = mapped_column(
        SAEnum(AnnouncementTarget, name="announcement_target_enum", native_enum=True, create_type=True),
        nullable=False, default=AnnouncementTarget.ALL,
    )
    announcement_type: Mapped[AnnouncementType] = mapped_column(
        SAEnum(AnnouncementType, name="announcement_type_enum", native_enum=True, create_type=True),
        nullable=False, default=AnnouncementType.GENERAL,
    )

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    starts_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_email: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
        comment="대상 사용자에게 이메일 동시 발송",
    )

    __table_args__ = (
        Index("ix_announcements_active_target", "is_active", "target_audience"),
        Index("ix_announcements_type", "announcement_type"),
    )

    def __repr__(self) -> str:
        return f"<Announcement id={self.id} '{self.title[:30]}' {self.announcement_type.value}>"
