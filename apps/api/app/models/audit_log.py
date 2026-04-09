"""AuditLog 모델 — API 호출 감사 로그.

모든 인증된 API 요청에 대해 미들웨어가 비동기적으로 기록한다.
민감한 필드(password, token 등)는 마스킹 처리된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditLog(Base):
    """API 호출 감사 로그."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),
    )

    # --- 누가 ---
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        comment="요청 사용자 — 비로그인 요청은 NULL",
    )
    user_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- 무엇을 ---
    method: Mapped[str] = mapped_column(String(10), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    query_string: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    request_body: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="요청 바디 (마스킹 적용) — POST/PUT/PATCH만",
    )

    # --- 결과 ---
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # --- 시간 ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_audit_logs_user_id_created_at", "user_id", text("created_at DESC")),
        Index("ix_audit_logs_path_method", "path", "method"),
        Index("ix_audit_logs_status_code", "status_code"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog id={self.id} {self.method} {self.path} "
            f"→ {self.status_code} ({self.latency_ms}ms)>"
        )
