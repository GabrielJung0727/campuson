"""OSCE 스테이션 + 실습 루브릭 + 실습 이벤트 모델 (v0.8).

실습 시험 모듈 강화:
1. OSCEExam: OSCE 시험 세트 (여러 스테이션 묶음)
2. OSCEStation: 개별 스테이션 (시나리오 + 시간제한 + 순서)
3. PracticumRubric: 실습 루브릭 템플릿
4. PracticumEvent: 실습 중 발생 이벤트 (시간초과/순서오류/위험행위)
5. PracticumReplay: ��습 리플레이 데이터
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
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department


class OSCEExam(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """OSCE 시험 — 여러 스테이션을 묶은 시험 세트."""

    __tablename__ = "osce_exams"

    school_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("schools.id", ondelete="SET NULL"),
        nullable=True,
    )
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_stations: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="총 스테이션 수",
    )
    time_per_station_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="600",
        comment="스테이션당 기본 ���간 (초)",
    )
    transition_time_sec: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="60",
        comment="스테이션 간 이동 시간 (초)",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    stations: Mapped[list["OSCEStation"]] = relationship(
        back_populates="exam", cascade="all, delete-orphan",
        order_by="OSCEStation.station_order",
    )

    __table_args__ = (
        Index("ix_osce_exams_dept", "department"),
        Index("ix_osce_exams_school", "school_id"),
    )


class OSCEStation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """OSCE 스테이션 — 시나리오와 연결된 개별 시험 스테이션."""

    __tablename__ = "osce_stations"

    exam_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("osce_exams.id", ondelete="CASCADE"),
        nullable=False,
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practicum_scenarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    station_order: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="스테이션 순서 (1부터)",
    )
    station_name: Mapped[str] = mapped_column(
        String(200), nullable=False, comment="스테이션 표시명",
    )
    time_limit_sec: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
        comment="스테이션별 시간 제한 (NULL이면 시험 기본값 사용)",
    )
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="1.0",
        comment="가중치 (시험 전체 점수 산출 시)",
    )
    instructions: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="스테이션 안내 문구",
    )

    exam: Mapped["OSCEExam"] = relationship(back_populates="stations")

    __table_args__ = (
        UniqueConstraint("exam_id", "station_order", name="uq_osce_station_order"),
        Index("ix_osce_stations_exam", "exam_id"),
    )


class PracticumRubric(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """실습 루브릭 템플릿.

    criteria: [{
        id: str,
        label: str,
        description: str,
        levels: [{level: 1, label: "미흡", score: 0}, {level: 2, ...}, ...]
    }]
    """

    __tablename__ = "practicum_rubrics"

    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb",
        comment="평가 기준 항목 리스트",
    )
    total_score: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="100",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practicum_scenarios.id", ondelete="SET NULL"),
        nullable=True,
        comment="연결된 시나리오 (NULL이면 범용 루브릭)",
    )

    __table_args__ = (
        Index("ix_practicum_rubrics_dept", "department"),
        Index("ix_practicum_rubrics_scenario", "scenario_id"),
    )


class PracticumEvent(Base, UUIDPrimaryKeyMixin):
    """실습 중 발생 이벤트 — 시간 초과, 순서 오류, 위험 행위 등.

    event_type: timeout | order_error | critical_miss | danger | custom
    """

    __tablename__ = "practicum_events"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practicum_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="timeout | order_error | critical_miss | danger | custom",
    )
    event_data: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
        comment="이벤트 상세 데이터 (item_id, expected_order, actual_order 등)",
    )
    timestamp_sec: Mapped[float] = mapped_column(
        Float, nullable=False, comment="세션 시작 이후 경과 시간 (초)",
    )
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="'warning'",
        comment="info | warning | critical",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("ix_practicum_events_session", "session_id"),
        Index("ix_practicum_events_type", "event_type"),
    )


class PracticumReplay(Base, UUIDPrimaryKeyMixin):
    """실습 리플레이 — 단계별 수행 기록 + 타임라인.

    steps: [{
        step_no: 1,
        item_id: str,
        action: "check" | "skip" | "error",
        timestamp_sec: float,
        duration_sec: float,
        notes: str | null
    }]
    """

    __tablename__ = "practicum_replays"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("practicum_sessions.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    total_duration_sec: Mapped[float] = mapped_column(
        Float, nullable=False, comment="전체 소요 시간 (초)",
    )
    steps: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="'[]'::jsonb",
        comment="단계별 수행 기록 타임라인",
    )
    video_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="녹화 영상 URL",
    )
    video_thumbnail_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="썸네일 URL",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )

    __table_args__ = (
        Index("ix_practicum_replays_session", "session_id"),
    )
