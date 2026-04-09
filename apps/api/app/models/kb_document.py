"""KBDocument & KBChunk 모델 — RAG 지식베이스.

설계 원칙
--------
- **1 문서 : N 청크** 관계. 문서는 원본 전체를 보존하고, 청크는 임베딩 저장 단위.
- **버전 관리**: `version` 컬럼으로 재적재 시 증가. 이전 버전은 archived로 유지 가능.
- **검수 상태**: DRAFT → REVIEWED → PUBLISHED → ARCHIVED 워크플로우.
- **임베딩 차원**: settings.embedding_dimensions (기본 1536).
  pgvector HNSW 인덱스 차원 제한(<=2000)을 고려해 text-embedding-3-large 사용 시에도
  OpenAI `dimensions` 파라미터로 1536 축소 권장.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import settings
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import Department, EmbeddingProvider, KBReviewStatus


class KBDocument(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """지식베이스 문서 — RAG 검색의 기본 단위 (1건 = 1 자료)."""

    __tablename__ = "kb_documents"

    # --- 분류 ---
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )

    # --- 본문 메타 ---
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="원본 전체 텍스트 (청킹 전)",
    )
    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="문서 요약 — Day 9 이후 LLM으로 자동 생성 가능",
    )

    # --- 출처/버전 ---
    source: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
        comment="출처 — 예: '제66회 간호사 국가시험 1교시 공식 해설'",
    )
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="버전 번호. 재적재 시 +1.",
    )

    # --- 검수 상태 ---
    review_status: Mapped[KBReviewStatus] = mapped_column(
        SAEnum(
            KBReviewStatus,
            name="kb_review_status_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=False,
        default=KBReviewStatus.DRAFT,
        server_default="DRAFT",
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="검수한 교수/관리자 ID",
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- 태그/메타 ---
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        server_default=text("'{}'::varchar[]"),
    )
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="페이지 수, 저자, 문서 유형 등 임의 메타",
    )

    # --- 통계 (적재 파이프라인에서 채움) ---
    total_chunks: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    # --- 관계 ---
    chunks: Mapped[list["KBChunk"]] = relationship(
        "KBChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
    )

    __table_args__ = (
        Index("ix_kb_documents_department_status", "department", "review_status"),
        Index("ix_kb_documents_tags_gin", "tags", postgresql_using="gin"),
        CheckConstraint("version >= 1", name="ck_kb_documents_version_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<KBDocument id={self.id} {self.department.value} "
            f"'{self.title[:30]}...' v{self.version} {self.review_status.value}>"
        )


class KBChunk(Base, UUIDPrimaryKeyMixin):
    """KBDocument를 청킹한 개별 조각 — 임베딩 검색의 실제 단위."""

    __tablename__ = "kb_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 상위 문서의 department를 복제해 검색 필터 속도를 높임 (비정규화)
    department: Mapped[Department] = mapped_column(
        SAEnum(Department, name="department_enum", native_enum=True, create_type=False),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="문서 내 0-indexed 청크 순번",
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # --- 벡터 임베딩 ---
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(settings.embedding_dimensions),
        nullable=True,
        comment="적재 초기에는 NULL, 임베딩 파이프라인이 채움",
    )
    embedding_provider: Mapped[EmbeddingProvider | None] = mapped_column(
        SAEnum(
            EmbeddingProvider,
            name="embedding_provider_enum",
            native_enum=True,
            create_type=True,
        ),
        nullable=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- 통계 ---
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    char_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- 메타 ---
    chunk_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="페이지 번호, 섹션, 스타일 등 청크 위치 메타",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    document: Mapped["KBDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_kb_chunks_document_index", "document_id", "chunk_index"),
        Index("ix_kb_chunks_department", "department"),
        # pgvector HNSW 인덱스는 Day 9 검색 API 구현 시 data 적재 후 생성 권장.
        # 여기서는 lookup 속도용 B-tree만 만들고, vector index는 마이그레이션 끝에 따로 추가.
    )

    def __repr__(self) -> str:
        has_emb = "emb" if self.embedding is not None else "no-emb"
        return (
            f"<KBChunk doc={self.document_id} #{self.chunk_index} "
            f"tokens={self.token_count} {has_emb}>"
        )
