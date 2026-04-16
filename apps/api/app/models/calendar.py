"""캘린더 / 일정 모델 (v0.8).

1. CalendarEvent: 학생/교수의 학습 일정 (과제 마감, 시험, 실습 등)
2. ProfessorComment: 교수 피드백 코멘트 (범용)
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

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class CalendarEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학습 일정 이벤트.

    event_type:
    - assignment_due: 과제 마감
    - exam: 시험 일정
    - practicum: 실습 시험
    - diagnostic: 진단 테스트
    - review: 복습 일정 (SRS)
    - custom: 사용자 정의
    """

    __tablename__ = "calendar_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="assignment_due | exam | practicum | diagnostic | review | custom",
    )
    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    end_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    all_day: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    # 연결 엔티티
    reference_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="assignment | osce_exam | practicum_session | diagnostic_test",
    )
    reference_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="연결 엔티티 ID",
    )
    color: Mapped[str | None] = mapped_column(
        String(7), nullable=True, comment="이벤트 색상 (hex)",
    )
    reminder_minutes: Mapped[int | None] = mapped_column(
        nullable=True, comment="사전 알림 (분)",
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    meta: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="추가 메타데이터",
    )

    __table_args__ = (
        Index("ix_calendar_events_user_date", "user_id", "start_at"),
        Index("ix_calendar_events_type", "event_type"),
        Index("ix_calendar_events_school", "school_id"),
    )


class ProfessorComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """교수 피드백 코멘트 — 범용.

    학습 이력, 과제 제출, 실습 세션 등 다양한 대상에 코멘트 가능.
    """

    __tablename__ = "professor_comments"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 대상 엔티티 (다형 관계)
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="learning_history | assignment_submission | practicum_session | general",
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        comment="대상 엔티티 ID (general이면 NULL)",
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="코멘트 본문",
    )
    is_private: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
        comment="교수만 볼 수 있는 메모 여부",
    )

    __table_args__ = (
        Index("ix_professor_comments_student", "student_id"),
        Index("ix_professor_comments_professor", "professor_id"),
        Index("ix_professor_comments_target", "target_type", "target_id"),
    )
