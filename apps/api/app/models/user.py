"""User 모델 — 학생/교수/관리자/개발자 통합 테이블."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department, Role, UserStatus


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

    # --- 감사 ---
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_users_department_role", "department", "role"),
        Index("ix_users_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email} role={self.role.value}>"
