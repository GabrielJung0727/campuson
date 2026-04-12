"""실습 평가 시스템 모델.

v0.4
------
- PracticumScenario: 학과별 실습 시나리오 템플릿 (체크리스트 포함)
- PracticumSession: 학생의 실습 수행 세션 + AI 피드백
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Enum as SAEnum

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    Department,
    EvalGrade,
    EvalStatus,
    PracticumCategory,
    PracticumMode,
)


class PracticumScenario(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """실습 시나리오 템플릿."""

    __tablename__ = "practicum_scenarios"
    __table_args__ = (
        Index("ix_practicum_scenarios_dept_cat", "department", "category"),
    )

    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    category: Mapped[PracticumCategory] = mapped_column(
        SAEnum(PracticumCategory, name="practicum_category_enum", native_enum=True, create_type=True),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # [{id, label, points, is_critical}]
    checklist_items: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="'[]'::jsonb")
    total_points: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    sessions: Mapped[list["PracticumSession"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan",
    )


class PracticumSession(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학생 실습 수행 세션."""

    __tablename__ = "practicum_sessions"
    __table_args__ = (
        Index("ix_practicum_sessions_student", "student_id"),
        Index("ix_practicum_sessions_scenario", "scenario_id"),
        Index("ix_practicum_sessions_status", "status"),
    )

    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("practicum_scenarios.id", ondelete="CASCADE"), nullable=False,
    )
    mode: Mapped[PracticumMode] = mapped_column(
        SAEnum(PracticumMode, name="practicum_mode_enum", native_enum=True, create_type=True),
        nullable=False, default=PracticumMode.SELF,
    )
    status: Mapped[EvalStatus] = mapped_column(
        SAEnum(EvalStatus, name="eval_status_enum", native_enum=True, create_type=True),
        nullable=False, default=EvalStatus.DRAFT,
    )
    join_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    video_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    video_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # [{item_id, status: "success"|"partial"|"fail"|"danger", points_earned}]
    checklist_results: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grade: Mapped[EvalGrade | None] = mapped_column(
        SAEnum(EvalGrade, name="eval_grade_enum", native_enum=True, create_type=True),
        nullable=True,
    )

    # {good: [str], needs_improvement: [str], suggestions: [str]}
    ai_feedback: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    professor_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
    )

    scenario: Mapped["PracticumScenario"] = relationship(back_populates="sessions")
