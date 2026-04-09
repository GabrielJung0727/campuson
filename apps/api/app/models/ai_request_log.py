"""AIRequestLog 모델 — LLM 호출 감사/디버깅/비용 추적 로그.

모든 LLM 호출은 이 테이블에 기록된다. AuditLog와 별개:
- AuditLog: HTTP API 레벨 (모든 요청)
- AIRequestLog: LLM 호출 레벨 (프롬프트/응답/토큰/지연시간)

향후 Day 9 RAG 통합 시 `retrieved_docs` 컬럼이 활용된다.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
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
from app.models.enums import AIRequestType, LLMProvider


class AIRequestLog(Base, UUIDPrimaryKeyMixin):
    """LLM 호출 1건의 기록."""

    __tablename__ = "ai_request_logs"

    # --- 누가 ---
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="비로그인/시스템 호출은 NULL",
    )

    # --- 무엇을 ---
    request_type: Mapped[AIRequestType] = mapped_column(
        SAEnum(
            AIRequestType,
            name="ai_request_type_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
    )
    template_name: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="사용된 프롬프트 템플릿 식별자"
    )

    # --- 컨텍스트 ---
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        comment="EXPLAIN 등 문제 컨텍스트가 있을 때",
    )

    # --- 입력 ---
    input_text: Mapped[str] = mapped_column(
        Text, nullable=False, comment="사용자 질문 또는 시스템 입력"
    )
    rendered_prompt: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="템플릿에 컨텍스트를 끼워 만든 최종 프롬프트 (디버깅용)",
    )
    retrieved_docs: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="RAG 검색 결과 — Day 9 KB 적재 후 활용",
    )

    # --- 출력 ---
    output_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # --- 모델 / 비용 ---
    provider: Mapped[LLMProvider] = mapped_column(
        SAEnum(
            LLMProvider,
            name="llm_provider_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- 결과 ---
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_ai_request_logs_user_created", "user_id", "created_at"),
        Index("ix_ai_request_logs_type_created", "request_type", "created_at"),
        Index("ix_ai_request_logs_success", "success"),
    )

    def __repr__(self) -> str:
        return (
            f"<AIRequestLog id={self.id} {self.request_type.value} "
            f"{self.provider.value}/{self.model} {self.latency_ms}ms "
            f"{'OK' if self.success else 'FAIL'}>"
        )
