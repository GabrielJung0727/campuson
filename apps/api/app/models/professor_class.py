"""교수 클래스 관리 모델 — 교수-학생 연결 시스템.

v0.2 기능
--------
- ProfessorClass: 교수가 생성하는 반/클래스 (예: "간호학과 24학번 1반")
- ClassStudent: 클래스-학생 N:M 매핑
- 교수는 여러 클래스를 가질 수 있고, 학생은 여러 클래스에 속할 수 있음
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class ProfessorClass(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """교수의 반(클래스)."""

    __tablename__ = "professor_classes"

    professor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="예: '간호학과 24학번 1반'"
    )
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, comment="학년도 (예: 2026)")
    semester: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="학기 (1 또는 2)")

    students: Mapped[list["ClassStudent"]] = relationship(
        "ClassStudent", back_populates="professor_class", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_professor_classes_professor", "professor_id"),
    )

    def __repr__(self) -> str:
        return f"<ProfessorClass id={self.id} '{self.class_name}' {self.department.value}>"


class ClassStudent(Base, UUIDPrimaryKeyMixin):
    """클래스-학생 N:M 매핑."""

    __tablename__ = "class_students"

    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professor_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    professor_class: Mapped["ProfessorClass"] = relationship(back_populates="students")

    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_students"),
        Index("ix_class_students_student", "student_id"),
    )

    def __repr__(self) -> str:
        return f"<ClassStudent class={self.class_id} student={self.student_id}>"
