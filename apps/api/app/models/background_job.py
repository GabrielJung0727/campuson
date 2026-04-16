"""BackgroundJob 모델 — 비동기 작업 상태 추적 (v0.6).

모든 백그라운드 작업(PDF 처리, 임베딩 생성, 대량 생성, 통계 집계 등)의
상태를 추적하는 테이블. 사용자는 이 테이블을 조회하여 작업 진행률을 확인한다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin
from app.models.enums import JobStatus, JobType


class BackgroundJob(Base, UUIDPrimaryKeyMixin):
    """비동기 작업 상태 추적."""

    __tablename__ = "background_jobs"

    # --- 작업 유형 ---
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, name="job_type_enum", native_enum=True, create_type=True),
        nullable=False,
    )

    # --- 상태 ---
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status_enum", native_enum=True, create_type=True),
        nullable=False,
        default=JobStatus.PENDING,
    )

    # --- 소유자 ---
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- 진행률 ---
    progress: Mapped[float] = mapped_column(Float, default=0.0, comment="0.0 ~ 1.0")
    progress_message: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- 입력/출력 ---
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- 재시도 ---
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # --- 타이밍 ---
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_bg_jobs_status", "status"),
        Index("ix_bg_jobs_type_status", "job_type", "status"),
        Index("ix_bg_jobs_created_by", "created_by"),
        Index("ix_bg_jobs_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<BackgroundJob {self.id} {self.job_type.value} {self.status.value} {self.progress:.0%}>"
