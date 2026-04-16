"""User 모델 — 학생/교수/관리자/개발자 통합 테이블."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    AdminRole,
    Department,
    ProfessorRole,
    Role,
    StudentNationality,
    UserStatus,
)


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """모든 사용자 (학생/교수/관리자/개발자) 통합 테이블.

    역할은 `role`로 구분하고 학과 스코프는 `department`로 결정한다.
    학생만 `student_no`를 가지며, 교수/관리자는 NULL 허용.
    """

    __tablename__ = "users"

    # --- 인증 ---
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    # --- 이메일 인증 ---
    email_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        comment="이메일 인증 완료 여부",
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="이메일 인증 완료 시각",
    )

    # --- 프로필 ---
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    student_no: Mapped[str | None] = mapped_column(
        String(20),
        unique=True,
        nullable=True,
        comment="학번 — 학생만 해당, 교수/관리자는 NULL",
    )

    # --- 권한 ---
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True),
        nullable=False,
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="role_enum", native_enum=True),
        nullable=False,
        default=Role.STUDENT,
    )
    status: Mapped[UserStatus] = mapped_column(
        SAEnum(UserStatus, name="user_status_enum", native_enum=True),
        nullable=False,
        default=UserStatus.PENDING,
    )

    # --- v0.3 역할 세분화 ---
    professor_role: Mapped[ProfessorRole | None] = mapped_column(
        SAEnum(ProfessorRole, name="professor_role_enum", native_enum=True, create_type=True),
        nullable=True,
        comment="교수 세부 역할 (전임/겸임/학과장)",
    )
    admin_role: Mapped[AdminRole | None] = mapped_column(
        SAEnum(AdminRole, name="admin_role_enum", native_enum=True, create_type=True),
        nullable=True,
        comment="관리자 세부 역할 (교무처/학생처/사무국 등)",
    )
    nationality: Mapped[StudentNationality | None] = mapped_column(
        SAEnum(StudentNationality, name="nationality_enum", native_enum=True, create_type=True),
        nullable=True,
        comment="학생 국적 (한국인/외국인)",
    )
    grade: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="학년 (1~4)",
    )

    # --- v0.8 멀티테넌시 ---
    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
        comment="소속 학교 (멀티테넌시)",
    )

    # --- 감사 ---
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_users_department_role", "department", "role"),
        Index("ix_users_status", "status"),
        Index("ix_users_school", "school_id"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role.value}>"
