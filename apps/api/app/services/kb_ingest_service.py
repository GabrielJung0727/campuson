"""KB 적재 파이프라인 — 문서 생성 → 청킹 → 임베딩 → 저장.

Day 8 기준
---------
- 문서 단위 동기 파이프라인 (API 또는 스크립트에서 호출)
- 청킹 전략은 `services.chunking.chunk_text` 사용
- 임베딩은 `core.embeddings.get_embedding_gateway` 사용 (Mock fallback 지원)

향후 확장 (Day 9+)
-----------------
- 대용량 문서의 background worker 처리
- 재적재 시 이전 버전 archive + 새 버전 생성
- 부분 재인덱싱 (변경된 청크만)
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedding_gateway
from app.models.enums import Department, KBReviewStatus
from app.models.kb_document import KBChunk, KBDocument
from app.services.chunking import Chunk, chunk_text

logger = logging.getLogger(__name__)


class KBIngestError(Exception):
    pass


class DocumentNotFoundError(KBIngestError):
    pass


@dataclass
class IngestRequest:
    """문서 적재 요청."""

    department: Department
    title: str
    content: str
    source: str | None = None
    source_url: str | None = None
    source_year: int | None = None
    tags: list[str] | None = None
    extra_metadata: dict | None = None
    review_status: KBReviewStatus = KBReviewStatus.DRAFT


@dataclass
class IngestResult:
    """적재 결과."""

    document_id: uuid.UUID
    total_chunks: int
    total_tokens: int
    embedded_chunks: int
    embedding_model: str
    embedding_dimensions: int


async def ingest_document(db: AsyncSession, payload: IngestRequest) -> IngestResult:
    """문서 1건을 청킹 + 임베딩 + 저장.

    실패 복원력
    ----------
    - 청킹 실패 시 → KBIngestError
    - 임베딩 실패 시 → chunk는 저장하되 embedding은 NULL로 둠 (향후 재시도 가능)
    """
    if not payload.content.strip():
        raise KBIngestError("Empty content")

    # 1) 청킹
    chunks: list[Chunk] = chunk_text(payload.content)
    if not chunks:
        raise KBIngestError("Chunking produced 0 chunks")

    total_tokens = sum(c.token_count for c in chunks)

    # 2) KBDocument INSERT
    doc = KBDocument(
        department=payload.department,
        title=payload.title,
        content=payload.content,
        source=payload.source,
        source_url=payload.source_url,
        source_year=payload.source_year,
        tags=payload.tags or [],
        extra_metadata=payload.extra_metadata,
        review_status=payload.review_status,
        total_chunks=len(chunks),
        total_tokens=total_tokens,
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)

    # 3) 임베딩 계산
    gateway = get_embedding_gateway()
    texts = [c.content for c in chunks]
    embedded_count = 0
    embedding_model = gateway.model
    embedding_dims = gateway.dimensions
    provider_enum = gateway.provider_name

    try:
        result = await gateway.embed_batch(texts)
        vectors = result.vectors
        embedding_model = result.model
        embedding_dims = result.dimensions
    except Exception as exc:  # noqa: BLE001
        logger.exception("Embedding failed for document %s — storing chunks without vectors", doc.id)
        vectors = [None] * len(chunks)  # type: ignore[list-item]

    # 4) KBChunk INSERT
    for chunk, vector in zip(chunks, vectors, strict=False):
        has_emb = vector is not None
        db.add(
            KBChunk(
                document_id=doc.id,
                department=payload.department,
                chunk_index=chunk.index,
                content=chunk.content,
                embedding=vector,
                embedding_provider=provider_enum if has_emb else None,
                embedding_model=embedding_model if has_emb else None,
                embedding_dimensions=embedding_dims if has_emb else None,
                token_count=chunk.token_count,
                char_count=chunk.char_count,
                chunk_metadata=chunk.metadata,
            )
        )
        if has_emb:
            embedded_count += 1

    await db.flush()
    logger.info(
        "KB ingest: doc=%s chunks=%d embedded=%d provider=%s model=%s",
        doc.id,
        len(chunks),
        embedded_count,
        provider_enum.value,
        embedding_model,
    )
    return IngestResult(
        document_id=doc.id,
        total_chunks=len(chunks),
        total_tokens=total_tokens,
        embedded_chunks=embedded_count,
        embedding_model=embedding_model,
        embedding_dimensions=embedding_dims,
    )


async def get_document(db: AsyncSession, document_id: uuid.UUID) -> KBDocument:
    doc = await db.get(KBDocument, document_id)
    if doc is None:
        raise DocumentNotFoundError(f"KBDocument {document_id} not found")
    return doc


async def delete_document(db: AsyncSession, document_id: uuid.UUID) -> None:
    doc = await get_document(db, document_id)
    await db.delete(doc)
    await db.flush()


async def list_documents(
    db: AsyncSession,
    *,
    department: Department | None = None,
    review_status: KBReviewStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[KBDocument]:
    stmt = select(KBDocument)
    if department:
        stmt = stmt.where(KBDocument.department == department)
    if review_status:
        stmt = stmt.where(KBDocument.review_status == review_status)
    stmt = (
        stmt.order_by(KBDocument.created_at.desc())
        .offset(max(0, offset))
        .limit(max(1, min(200, limit)))
    )
    return list((await db.execute(stmt)).scalars().all())


async def mark_reviewed(
    db: AsyncSession,
    document_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    *,
    publish: bool = False,
) -> KBDocument:
    """문서 검수 완료 표시."""
    doc = await get_document(db, document_id)
    doc.review_status = KBReviewStatus.PUBLISHED if publish else KBReviewStatus.REVIEWED
    doc.reviewed_by = reviewer_id
    doc.reviewed_at = datetime.now(UTC)
    await db.flush()
    await db.refresh(doc)
    return doc
