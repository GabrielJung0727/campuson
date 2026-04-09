"""DiagnosticTest / DiagnosticAnswer 모델.

진단 테스트는 학생당 1회 응시하는 초기 평가이며, 결과는 AIProfile 생성의 입력이 된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Level


class DiagnosticTest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학생의 진단 테스트 1건.

    상태 흐름
    --------
    1. POST /diagnostic/start  → started_at 기록, completed_at NULL
    2. POST /diagnostic/{id}/submit → completed_at, total_score, section_scores, weak_areas, level 채워짐
    """

    __tablename__ = "diagnostic_tests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )

    # --- 시간 ---
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- 채점 결과 ---
    total_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="0.0 ~ 1.0 (정답률)"
    )
    section_scores: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment='과목별 정답률 — 예: {"성인간호학": 0.72, "기본간호학": 0.55}',
    )
    weak_areas: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="취약영역 우선순위 배열 — [{subject, unit, score, priority}]",
    )
    level: Mapped[Level | None] = mapped_column(
        SAEnum(Level, name="level_enum", native_enum=True, create_type=True),
        nullable=True,
    )

    # --- 관계 ---
    answers: Mapped[list["DiagnosticAnswer"]] = relationship(
        "DiagnosticAnswer",
        back_populates="test",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        # 학생당 1회 정책 — DB 레벨 (NULL이 아닌 completed_at 기준이 아니라
        # user_id에 unique를 걸면 한 번만 시작 가능)
        UniqueConstraint("user_id", name="uq_diagnostic_tests_user_id"),
    )

    def __repr__(self) -> str:
        status = "completed" if self.completed_at else "in_progress"
        return f"<DiagnosticTest id={self.id} user={self.user_id} {status}>"


class DiagnosticAnswer(Base, UUIDPrimaryKeyMixin):
    """진단 테스트의 문항별 응답."""

    __tablename__ = "diagnostic_answers"

    test_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("diagnostic_tests.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    selected_choice: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="0-indexed 선택 번호"
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    time_spent_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    test: Mapped["DiagnosticTest"] = relationship(back_populates="answers")

    __table_args__ = (
        UniqueConstraint(
            "test_id", "question_id", name="uq_diagnostic_answers_test_question"
        ),
        Index("ix_diagnostic_answers_test_id", "test_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<DiagnosticAnswer test={self.test_id} q={self.question_id} "
            f"sel={self.selected_choice} {'O' if self.is_correct else 'X'}>"
        )
