"""CostDaily 모델 — 일별 LLM 비용 집계 (v0.6).

AIRequestLog를 일별로 집계한 캐시 테이블.
provider/model/role별 토큰 사용량과 추정 비용을 저장한다.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class CostDaily(Base, UUIDPrimaryKeyMixin):
    """일별 LLM 비용 집계."""

    __tablename__ = "cost_daily"

    # --- 집계 키 ---
    date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, comment="ANTHROPIC|OPENAI|MOCK")
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, comment="STUDENT|PROFESSOR|ADMIN|DEVELOPER|SYSTEM")
    department: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- 사용량 ---
    request_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, default=0)
    total_tokens: Mapped[int] = mapped_column(BigInteger, default=0)

    # --- 비용 (USD) ---
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)

    # --- 성능 ---
    avg_latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    p95_latency_ms: Mapped[int] = mapped_column(Integer, default=0)

    # --- 캐시 ---
    cache_hit_count: Mapped[int] = mapped_column(Integer, default=0, comment="동일 질문 캐시 히트")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("date", "provider", "model", "role", "department", name="uq_cost_daily_key"),
        Index("ix_cost_daily_date", "date"),
        Index("ix_cost_daily_provider", "provider"),
    )
