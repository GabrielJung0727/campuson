"""학교(테넌트) 모델 — 멀티테넌시 지원 (v0.8).

1. School: 학교 단위 테넌트 (school_id)
2. SchoolSettings: 학교별 설정 (��랜딩, LLM 정책, 비용 한도)
3. SchoolDepartment: 학교-학과 매핑 (학과별 세부 설정)
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
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class School(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학교 — 멀티테넌시 최상�� 엔티티.

    모든 데이터(User, Question, KB 등)는 school_id로 격리된다.
    """

    __tablename__ = "schools"

    name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="학교명 (예: 경복대학교)"
    )
    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False,
        comment="학교 코드 (예: KYUNGBOK, URL slug 용)",
    )
    domain: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="학교 이메일 도메인 (예: kyungbok.ac.kr)",
    )
    logo_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="학교 로고 URL",
    )
    primary_color: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default="'#2563EB'",
        comment="브랜드 메인 컬러 (hex)",
    )
    secondary_color: Mapped[str] = mapped_column(
        String(7), nullable=False, server_default="'#1E40AF'",
        comment="브랜드 보조 컬러 (hex)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )

    # 관계
    settings: Mapped["SchoolSettings | None"] = relationship(
        back_populates="school", uselist=False, cascade="all, delete-orphan",
    )
    departments: Mapped[list["SchoolDepartment"]] = relationship(
        back_populates="school", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_schools_code", "code"),
        Index("ix_schools_domain", "domain"),
    )


class SchoolSettings(Base, UUIDPrimaryKeyMixin):
    """학교별 상세 설정 (LLM 정책, 비용 한도, SSO 등)."""

    __tablename__ = "school_settings"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    # LLM 정책
    llm_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="'anthropic'",
        comment="기본 LLM 프로바이더",
    )
    llm_model: Mapped[str] = mapped_column(
        String(100), nullable=False, server_default="'claude-sonnet-4-6'",
        comment="기본 LLM 모델",
    )
    daily_token_limit_student: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="50000",
        comment="학생 일일 토큰 한도",
    )
    daily_token_limit_professor: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="200000",
        comment="교수 일일 토큰 한도",
    )
    monthly_cost_limit_usd: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="500.0",
        comment="월간 비용 한도 (USD)",
    )

    # SSO
    sso_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    sso_provider: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="saml | oidc | oauth2",
    )
    sso_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="SSO 설정 (entity_id, login_url, certificate 등)",
    )

    # LMS
    lms_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    lms_platform: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="lti13 | canvas | blackboard | moodle",
    )
    lms_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="LMS 설정 (client_id, auth_url, token_url 등)",
    )

    # 기타
    custom_settings: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="학교별 커스텀 설정",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
    )

    school: Mapped["School"] = relationship(back_populates="settings")


class SchoolDepartment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """학교-학과 매핑 — 학��별 학과 활성화 + 세부 설정."""

    __tablename__ = "school_departments"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    head_professor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="학과장",
    )
    student_count_limit: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="학과 최대 학생 수",
    )
    custom_blueprint: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="학교 자체 블루프린트 오버라이드",
    )

    school: Mapped["School"] = relationship(back_populates="departments")

    __table_args__ = (
        UniqueConstraint("school_id", "department", name="uq_school_department"),
        Index("ix_school_departments_school", "school_id"),
    )
