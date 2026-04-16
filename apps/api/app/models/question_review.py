"""문항 검수 워크플로우 모델 (v0.5).

교수가 AI 생성 문제 및 해설을 검수하는 프로세스:
- PENDING_REVIEW: AI 생성 후 검수 대기
- APPROVED: 교수 승인 → 학생에게 공개
- REJECTED: 반려 (사유 포함)
- REVISION_REQUESTED: 수정 요청

문항 수정 이력(QuestionEditHistory)으로 변경 추적.
교수 코멘트는 버전 관리됨.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import QuestionReviewStatus


class QuestionReview(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """문항 검수 레코드 — 1 문항에 N개의 검수 기록 가능."""

    __tablename__ = "question_reviews"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    reviewer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="검수 교수 ID (NULL이면 아직 미할당)",
    )
    status: Mapped[QuestionReviewStatus] = mapped_column(
        SAEnum(
            QuestionReviewStatus,
            name="question_review_status_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
        default=QuestionReviewStatus.PENDING_REVIEW,
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="교수 코멘트 (승인/반려 사유)",
    )
    ai_explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="AI가 생성한 해설 원본",
    )
    professor_explanation: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="교수가 수정/승인한 공식 해설",
    )
    review_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="검수 버전 (같은 문항에 대한 재검수 시 증가)",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_question_reviews_question", "question_id"),
        Index("ix_question_reviews_reviewer", "reviewer_id"),
        Index("ix_question_reviews_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<QuestionReview id={self.id} question={self.question_id} "
            f"status={self.status.value} v{self.review_version}>"
        )


class QuestionEditHistory(Base, UUIDPrimaryKeyMixin):
    """문항 수정 이력 — 누가, 언제, 무엇을 바꿨는지 추적."""

    __tablename__ = "question_edit_history"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    editor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="수정자 (교수/관리자/AI)",
    )
    edit_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="수정 유형: CREATE, UPDATE, REVIEW_APPROVE, REVIEW_REJECT, AI_GENERATE",
    )
    changes: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="변경 내역 — {field: {old: ..., new: ...}}",
    )
    comment: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="수정 사유/코멘트",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_question_edit_history_question", "question_id"),
        Index("ix_question_edit_history_editor", "editor_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<QuestionEditHistory id={self.id} question={self.question_id} "
            f"type={self.edit_type}>"
        )
