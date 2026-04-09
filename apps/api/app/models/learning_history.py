"""LearningHistory 모델 — 학생 풀이 이력.

특징
----
- 매 풀이마다 새 row가 추가된다 (모든 attempt 보존 → 풀이 시간/정확도 추이 분석)
- `attempt_no`는 동일 (user, question)에 대한 누적 풀이 횟수 (1부터 시작)
- 정답이면 `error_type`은 NULL
- AI 피드백은 Day 6/10 LLM 연동 후 채워짐 (현재는 NULL 가능)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import ErrorType


class LearningHistory(Base, UUIDPrimaryKeyMixin):
    """학생의 문제 풀이 이력 1건."""

    __tablename__ = "learning_history"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- 풀이 결과 ---
    selected_choice: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0-indexed 선택 번호"
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    solving_time_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # --- 오답 분류 (정답이면 NULL) ---
    error_type: Mapped[ErrorType | None] = mapped_column(
        SAEnum(ErrorType, name="error_type_enum", native_enum=True, create_type=True),
        nullable=True,
    )

    # --- 누적 풀이 횟수 (이 풀이가 몇 번째 시도인가) ---
    attempt_no: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default="1",
        comment="동일 (user, question)에 대한 1-indexed 누적 풀이 횟수",
    )

    # --- AI 피드백 (Day 6/10에서 채워짐) ---
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_learning_history_user_created", "user_id", "created_at"),
        Index(
            "ix_learning_history_user_question",
            "user_id",
            "question_id",
            "created_at",
        ),
        Index("ix_learning_history_user_correct", "user_id", "is_correct"),
    )

    def __repr__(self) -> str:
        return (
            f"<LearningHistory user={self.user_id} q={self.question_id} "
            f"{'O' if self.is_correct else 'X'} attempt={self.attempt_no}>"
        )
