"""KB 관련 Pydantic 스키마 — 적재/조회/검색."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Department, KBReviewStatus


# === 적재 ===
class KBIngestRequest(BaseModel):
    """문서 적재 요청 (관리자 전용)."""

    department: Department
    title: str = Field(..., min_length=1, max_length=300)
    content: str = Field(..., min_length=10)
    source: str | None = Field(default=None, max_length=300)
    source_url: str | None = Field(default=None, max_length=500)
    source_year: int | None = Field(default=None, ge=1990, le=2100)
    tags: list[str] = Field(default_factory=list, max_length=20)
    extra_metadata: dict | None = None
    review_status: KBReviewStatus = KBReviewStatus.DRAFT


class KBIngestResponse(BaseModel):
    """적재 결과."""

    document_id: uuid.UUID
    total_chunks: int
    total_tokens: int
    embedded_chunks: int
    embedding_model: str
    embedding_dimensions: int


# === 조회 ===
class KBDocumentResponse(BaseModel):
    """문서 요약 응답 (목록)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    department: Department
    title: str
    summary: str | None = None
    source: str | None
    source_url: str | None
    source_year: int | None
    version: int
    review_status: KBReviewStatus
    tags: list[str]
    total_chunks: int
    total_tokens: int
    created_at: datetime
    updated_at: datetime


class KBDocumentListResponse(BaseModel):
    items: list[KBDocumentResponse]
    total: int
    limit: int
    offset: int


# === 검수 ===
class KBReviewRequest(BaseModel):
    publish: bool = Field(
        default=False,
        description="True면 PUBLISHED, False면 REVIEWED 상태로 변경",
    )


# === 검색 ===
class KBSearchRequest(BaseModel):
    """하이브리드 검색 요청."""

    query: str = Field(..., min_length=1, max_length=500)
    department: Department | None = None
    tags: list[str] | None = None
    source_year: int | None = None
    top_k: int = Field(default=10, ge=1, le=50)
    candidate_limit: int = Field(default=50, ge=5, le=200)
    use_vector: bool = True
    use_lexical: bool = True
    rerank: bool = Field(
        default=True,
        description="Stage 2 리랭커 적용 여부 (Day 9는 룰 베이스)",
    )
    include_unpublished: bool = Field(
        default=False,
        description="PUBLISHED 외의 상태도 포함 (관리자만 허용)",
    )


class KBSearchHit(BaseModel):
    """검색 결과 1건."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    department: Department
    chunk_index: int
    content: str
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    # 점수 계열
    vector_score: float | None = None
    lexical_score: float | None = None
    vector_rank: int | None = None
    lexical_rank: int | None = None
    rrf_score: float
    rerank_score: float | None = None
    rerank_signals: dict[str, float] | None = None


class KBSearchResponse(BaseModel):
    query: str
    total: int
    reranked: bool
    reranker_name: str | None = None
    hits: list[KBSearchHit]


SearchMode = Literal["hybrid", "vector", "lexical"]
