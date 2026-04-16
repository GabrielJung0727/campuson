"""LMS 연동 모델 (v0.8).

1. LMSCourse: LMS 연동 과목 매핑
2. LMSGradeSync: 성적 연동 이력
3. SSOSession: SSO 세션 추적
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class LMSCourse(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """LMS 연동 과목 매핑.

    CampusON의 ProfessorClass와 외부 LMS의 과목을 연결한다.
    """

    __tablename__ = "lms_courses"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    class_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("professor_classes.id", ondelete="CASCADE"),
        nullable=False,
    )
    lms_course_id: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="외부 LMS 과목 ID",
    )
    lms_course_name: Mapped[str | None] = mapped_column(
        String(300), nullable=True, comment="외부 LMS 과목명",
    )
    lms_platform: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="lti13 | canvas | blackboard | moodle",
    )
    sync_grades: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
        comment="성적 자동 동기화 여부",
    )
    grade_column_id: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
        comment="LMS 성적부 컬럼 ID (성적 전송 대상)",
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="연동 설정 (custom_params 등)",
    )

    __table_args__ = (
        UniqueConstraint("school_id", "lms_course_id", name="uq_lms_course"),
        Index("ix_lms_courses_school", "school_id"),
        Index("ix_lms_courses_class", "class_id"),
    )


class LMSGradeSync(Base, UUIDPrimaryKeyMixin):
    """성적 연동 이력 — LMS로 전송한 성적 기록."""

    __tablename__ = "lms_grade_syncs"

    lms_course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lms_courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    score: Mapped[float] = mapped_column(
        Float, nullable=False, comment="전송 점수 (0.0~100.0)",
    )
    score_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="quiz | assignment | diagnostic | practicum",
    )
    source_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
        comment="원본 데이터 ID (과제ID, 진단ID 등)",
    )
    lms_response: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="LMS 응답 데이터",
    )
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("ix_lms_grade_syncs_course", "lms_course_id"),
        Index("ix_lms_grade_syncs_student", "student_id"),
    )


class SSOSession(Base, UUIDPrimaryKeyMixin):
    """SSO 세션 추적 — 외부 IdP 인증 세션."""

    __tablename__ = "sso_sessions"

    school_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    sso_provider: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="saml | oidc | oauth2",
    )
    external_id: Mapped[str] = mapped_column(
        String(300), nullable=False, comment="외부 IdP 사용자 ID",
    )
    session_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, comment="세션 메타 (attributes, groups 등)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        Index("ix_sso_sessions_school_user", "school_id", "user_id"),
        Index("ix_sso_sessions_external", "school_id", "external_id"),
    )
