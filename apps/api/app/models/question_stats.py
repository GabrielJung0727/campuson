"""문항별 응답 통계 + 학생 행동 트래킹 모델.

v0.2 기능 확장
-----------
1. **QuestionStats**: 문항별 응답 통계 캐시 (정답률, 선택지별 선택률, 응시자 수)
2. **AnswerInteraction**: 학생 행동 트래킹 (고민 시간, 선택 변경, 첫 클릭)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class QuestionStats(Base, UUIDPrimaryKeyMixin):
    """문항별 응답 통계 캐시.

    학습 이력에서 집계한 결과를 캐시하여 빠른 조회.
    주기적으로 또는 풀이 제출 시 갱신.
    """

    __tablename__ = "question_stats"

    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # --- 집계 ---
    total_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    correct_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    accuracy: Mapped[float] = mapped_column(
        nullable=False, default=0.0, server_default="0.0",
        comment="정답률 0.0~1.0",
    )

    # 선택지별 선택 횟수: {0: 12, 1: 87, 2: 30, 3: 15, 4: 6}
    choice_distribution: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        comment="선택지 인덱스별 선택 횟수",
    )

    # 평균 풀이 시간
    avg_time_sec: Mapped[float] = mapped_column(
        nullable=False, default=0.0, server_default="0.0",
    )
    # 평균 선택 변경 횟수
    avg_choice_changes: Mapped[float] = mapped_column(
        nullable=False, default=0.0, server_default="0.0",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_question_stats_accuracy", "accuracy"),
    )

    def __repr__(self) -> str:
        return f"<QuestionStats q={self.question_id} attempts={self.total_attempts} acc={self.accuracy:.2f}>"


class AnswerInteraction(Base, UUIDPrimaryKeyMixin):
    """학생 행동 트래킹 — 문제 풀이 중 고민 패턴 기록."""

    __tablename__ = "answer_interactions"

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("learning_history.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- 시간 ---
    time_spent_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="문제 진입~제출까지 총 소요 시간(초)",
    )
    time_to_first_click_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="문제 진입 후 첫 클릭까지 걸린 시간(ms)",
    )

    # --- 선택 변경 ---
    first_choice: Mapped[int] = mapped_column(
        Integer, nullable=False, default=-1,
        comment="최초 선택한 선택지 번호 (0-indexed, -1=선택 안 함)",
    )
    final_choice: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="최종 제출한 선택지 번호",
    )
    choice_changes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        comment="선택 변경 횟수 (0=한 번에 제출)",
    )
    choice_sequence: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="선택 이력: [{choice: 2, ts: 3400}, {choice: 0, ts: 8200}]",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_answer_interactions_user_question", "user_id", "question_id"),
        Index("ix_answer_interactions_question", "question_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<AnswerInteraction q={self.question_id} "
            f"first={self.first_choice} final={self.final_choice} "
            f"changes={self.choice_changes}>"
        )
