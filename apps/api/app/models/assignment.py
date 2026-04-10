"""과제 시스템 모델.

v0.2 P2
------
- Assignment: 교수가 출제하는 과제 (문제 세트 + 마감일)
- AssignmentSubmission: 학생의 과제 제출 결과
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class AssignmentStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    CLOSED = "CLOSED"


class Assignment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """교수가 출제하는 과제."""

    __tablename__ = "assignments"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    class_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("professor_classes.id", ondelete="SET NULL"), nullable=True,
        comment="특정 클래스 대상. NULL이면 학과 전체",
    )
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False), nullable=False
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[AssignmentStatus] = mapped_column(
        SAEnum(AssignmentStatus, name="assignment_status_enum", native_enum=True, create_type=True),
        nullable=False, default=AssignmentStatus.DRAFT,
    )

    # 문제 ID 목록 (questions 테이블 참조)
    question_ids: Mapped[list] = mapped_column(
        JSONB, nullable=False, comment="문제 UUID 배열"
    )
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    submissions: Mapped[list["AssignmentSubmission"]] = relationship(
        "AssignmentSubmission", back_populates="assignment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_assignments_professor", "professor_id"),
        Index("ix_assignments_class", "class_id"),
    )

    def __repr__(self) -> str:
        return f"<Assignment id={self.id} '{self.title}' {self.status.value}>"


class AssignmentSubmission(Base, UUIDPrimaryKeyMixin):
    """학생의 과제 제출 결과."""

    __tablename__ = "assignment_submissions"

    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    # 결과
    answers: Mapped[list] = mapped_column(
        JSONB, nullable=False,
        comment="[{question_id, selected_choice, is_correct, time_spent_sec}]",
    )
    total_correct: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_questions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    time_spent_sec: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assignment: Mapped["Assignment"] = relationship(back_populates="submissions")

    __table_args__ = (
        Index("ix_assignment_submissions_student", "student_id"),
        Index("ix_assignment_submissions_assignment", "assignment_id"),
    )
