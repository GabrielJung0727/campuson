"""AI 관련 Pydantic 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AIRequestType, LLMProvider


# === 요청 ===
class ExplainRequest(BaseModel):
    """문제 해설 요청 — 학생이 푼 문제(또는 푸는 문제)를 명시."""

    question_id: uuid.UUID
    history_id: uuid.UUID | None = Field(
        default=None,
        description="이미 제출한 풀이 이력의 id. 있으면 학생의 선택지/정오답을 자동 사용.",
    )


class QARequest(BaseModel):
    """자유 질의응답 요청."""

    question: str = Field(..., min_length=1, max_length=2000)


# === 응답 ===
class AIGenerationMetadata(BaseModel):
    """LLM 호출 메타데이터."""

    log_id: uuid.UUID
    provider: LLMProvider
    model: str
    template_name: str | None
    input_tokens: int
    output_tokens: int
    latency_ms: int


class CitationItem(BaseModel):
    """답변 내 인용 1건 (Day 10 RAG)."""

    number: int
    chunk_id: str
    document_id: str
    document_title: str
    source: str | None
    snippet: str


class AIGenerationResponse(BaseModel):
    """일반 LLM 응답 형식."""

    request_type: AIRequestType
    output_text: str
    metadata: AIGenerationMetadata
    rag_used: bool = False
    citations: list[CitationItem] = Field(default_factory=list)


# === AI 요청 로그 조회 ===
class AIRequestLogItem(BaseModel):
    """감사 로그 1건 (관리자/개발자 조회)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None
    request_type: AIRequestType
    template_name: str | None
    question_id: uuid.UUID | None
    provider: LLMProvider
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    success: bool
    error_message: str | None
    created_at: datetime


class AIRequestLogListResponse(BaseModel):
    items: list[AIRequestLogItem]
    total: int
    page: int
    page_size: int
    has_next: bool
