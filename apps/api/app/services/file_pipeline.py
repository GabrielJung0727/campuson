"""파일 처리 통합 파이프라인 (v0.9).

End-to-end 업로드 → 추출 → 청킹 → 임베딩 → 색인:
1. 파일 수신 (bytes)
2. 보안 스캔 (크기/MIME/매직바이트)
3. 텍스트 추출 (document_extraction)
4. 메타데이터 자동 태깅
5. 청킹 (chunking)
6. 임베딩 생성
7. KB DB 적재
8. 색인 확인 / 품질 리포트
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Department, KBReviewStatus
from app.models.kb_document import KBChunk, KBDocument
from app.services import document_extraction
from app.services.kb_ingest_service import IngestRequest, ingest_document

logger = logging.getLogger(__name__)


# === Security limits ===

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_MIME_PREFIXES = (
    "application/pdf",
    "application/vnd.openxmlformats",
    "application/msword",
    "text/",
    "application/x-markdown",
)
DANGEROUS_EXTENSIONS = {".exe", ".bat", ".sh", ".ps1", ".cmd", ".msi", ".dll"}


@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    document_id: uuid.UUID | None = None
    file_name: str = ""
    file_size: int = 0
    format: str = ""
    total_chunks: int = 0
    total_tokens: int = 0
    embedded_chunks: int = 0
    detected_tables: int = 0
    detected_images: int = 0
    auto_tags: list[str] = field(default_factory=list)
    security_warnings: list[str] = field(default_factory=list)
    extraction_errors: list[str] = field(default_factory=list)
    success: bool = False
    error_message: str | None = None


class FilePipelineError(Exception):
    pass


# === Security scan ===


def scan_file_security(
    content: bytes, filename: str | None = None, content_type: str | None = None,
) -> list[str]:
    """업로드 파일 기본 보안 스캔.

    Returns
    -------
    list[str]
        발견된 경고/에러 목록 (빈 리스트면 통과)
    """
    warnings: list[str] = []

    # 크기 제한
    if len(content) > MAX_FILE_SIZE:
        warnings.append(f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")

    if len(content) == 0:
        warnings.append("Empty file")

    # 위험 확장자
    if filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext in DANGEROUS_EXTENSIONS:
            warnings.append(f"Dangerous file extension: {ext}")

    # MIME 타입 화이트리스트
    if content_type:
        ct = content_type.lower().split(";")[0].strip()
        if not any(ct.startswith(p) for p in ALLOWED_MIME_PREFIXES):
            warnings.append(f"Content-Type not allowed: {ct}")

    # 매직 바이트 — 실행파일 시그니처 검출
    dangerous_signatures = [
        (b"MZ", "Windows executable (PE)"),
        (b"\x7fELF", "Linux executable (ELF)"),
        (b"\xca\xfe\xba\xbe", "Mach-O executable"),
    ]
    for sig, desc in dangerous_signatures:
        if content.startswith(sig):
            warnings.append(f"Executable signature detected: {desc}")

    # 과도한 제어문자 (바이너리일 가능성)
    if len(content) > 100:
        sample = content[:1000]
        control_ratio = sum(1 for b in sample if b < 9 or (14 <= b <= 31)) / len(sample)
        if control_ratio > 0.3 and not (content[:4] == b"%PDF" or content[:2] == b"PK"):
            warnings.append("High control-character ratio — possibly binary/corrupt")

    return warnings


# === Main pipeline ===


async def process_file(
    db: AsyncSession,
    *,
    content: bytes,
    filename: str,
    department: Department,
    title: str | None = None,
    content_type: str | None = None,
    source: str | None = None,
    source_url: str | None = None,
    source_year: int | None = None,
    extra_tags: list[str] | None = None,
    uploaded_by: uuid.UUID | None = None,
    strict_security: bool = True,
) -> PipelineResult:
    """파일 업로드 → 추출 → 청킹 → 임베딩 → 색인 전체 파이프라인.

    Parameters
    ----------
    strict_security : bool
        True면 보안 경고 발생 시 중단. False면 경고만 기록하고 진행.
    """
    result = PipelineResult(file_name=filename, file_size=len(content))

    # 1. 보안 스캔
    warnings = scan_file_security(content, filename, content_type)
    result.security_warnings = warnings
    if warnings and strict_security:
        fatal = [w for w in warnings if "Dangerous" in w or "Executable" in w or "too large" in w]
        if fatal:
            result.error_message = f"Security scan failed: {'; '.join(fatal)}"
            logger.warning("File rejected: %s — %s", filename, fatal)
            return result

    # 2. 텍스트 추출
    try:
        extracted = document_extraction.extract_from_bytes(content, filename, content_type)
        result.format = extracted.format
        result.detected_tables = extracted.detected_tables
        result.detected_images = extracted.detected_images
        result.extraction_errors = extracted.extraction_errors
    except Exception as exc:  # noqa: BLE001
        result.error_message = f"Extraction failed: {exc}"
        logger.exception("Extraction pipeline failed")
        return result

    if not extracted.text.strip():
        result.error_message = "No text content extracted"
        return result

    # 3. 자동 태깅
    auto_tags = document_extraction.auto_tag_content(extracted.text, department.value)
    if extra_tags:
        auto_tags = sorted(set(auto_tags) | set(extra_tags))
    result.auto_tags = auto_tags

    # 4. 블록 구조 메타데이터
    block_metadata = {
        "blocks": [
            {
                "type": b.type,
                "level": b.level,
                "metadata": b.metadata,
                "char_count": len(b.content),
            }
            for b in extracted.blocks
        ],
        "tables": extracted.detected_tables,
        "images": extracted.detected_images,
        "pages": extracted.total_pages,
        "source_filename": filename,
        "content_type": content_type,
        "uploaded_by": str(uploaded_by) if uploaded_by else None,
        "uploaded_at": datetime.now(UTC).isoformat(),
    }

    # 5. KB 적재 (청킹 + 임베딩 + DB 저장 — 기존 서비스 사용)
    ingest_req = IngestRequest(
        department=department,
        title=title or filename,
        content=extracted.text,
        source=source or "file_upload",
        source_url=source_url,
        source_year=source_year,
        tags=auto_tags,
        extra_metadata=block_metadata,
        review_status=KBReviewStatus.DRAFT,
    )

    try:
        ingest_result = await ingest_document(db, ingest_req)
        result.document_id = ingest_result.document_id
        result.total_chunks = ingest_result.total_chunks
        result.total_tokens = ingest_result.total_tokens
        result.embedded_chunks = ingest_result.embedded_chunks
        result.success = True
    except Exception as exc:  # noqa: BLE001
        result.error_message = f"Ingest failed: {exc}"
        logger.exception("KB ingest failed")

    return result


# === Quality evaluation ===


async def evaluate_search_quality(
    db: AsyncSession,
    test_queries: list[dict],
    *,
    department: Department | None = None,
) -> dict:
    """검색 품질 평가 (precision@k, recall@k).

    test_queries: [{"query": "...", "expected_doc_ids": ["uuid", ...]}]
    """
    from app.services.kb_search_service import hybrid_search

    total_queries = len(test_queries)
    precision_scores: list[float] = []
    recall_scores: list[float] = []
    mrr_scores: list[float] = []

    for tq in test_queries:
        query = tq["query"]
        expected_ids = set(tq.get("expected_doc_ids", []))
        k = tq.get("k", 5)

        try:
            results = await hybrid_search(
                db, query=query, department=department, top_k=k,
            )
            retrieved_ids = [str(r.get("document_id", "")) for r in results[:k]]

            # Precision@k
            hits = sum(1 for doc_id in retrieved_ids if doc_id in expected_ids)
            precision = hits / k if k > 0 else 0
            precision_scores.append(precision)

            # Recall@k
            recall = hits / len(expected_ids) if expected_ids else 0
            recall_scores.append(recall)

            # MRR
            rr = 0.0
            for rank, doc_id in enumerate(retrieved_ids, start=1):
                if doc_id in expected_ids:
                    rr = 1.0 / rank
                    break
            mrr_scores.append(rr)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Query '%s' failed: %s", query, exc)

    return {
        "total_queries": total_queries,
        "avg_precision_at_k": sum(precision_scores) / len(precision_scores) if precision_scores else 0,
        "avg_recall_at_k": sum(recall_scores) / len(recall_scores) if recall_scores else 0,
        "mean_reciprocal_rank": sum(mrr_scores) / len(mrr_scores) if mrr_scores else 0,
        "evaluated_at": datetime.now(UTC).isoformat(),
    }


# === Update / Delete propagation ===


async def reindex_document(
    db: AsyncSession, document_id: uuid.UUID,
) -> PipelineResult:
    """문서 재색인 — 기존 청크 제거 + 새로 임베딩.

    문서 내용이 업데이트되었을 때 호출.
    """
    doc = await db.get(KBDocument, document_id)
    if not doc:
        raise FilePipelineError(f"Document {document_id} not found")

    # 기존 청크 삭제
    existing_chunks = list((await db.execute(
        select(KBChunk).where(KBChunk.document_id == document_id)
    )).scalars().all())
    for chunk in existing_chunks:
        await db.delete(chunk)
    await db.flush()

    # 재적재
    from app.services.chunking import chunk_text
    from app.core.embeddings import get_embedding_gateway

    chunks = chunk_text(doc.content)
    gateway = get_embedding_gateway()

    try:
        emb_result = await gateway.embed_batch([c.content for c in chunks])
        vectors = emb_result.vectors
        embedding_model = emb_result.model
        embedding_dims = emb_result.dimensions
    except Exception as exc:  # noqa: BLE001
        logger.warning("Reindex embedding failed: %s", exc)
        vectors = [None] * len(chunks)
        embedding_model = gateway.model
        embedding_dims = gateway.dimensions

    embedded = 0
    for chunk, vec in zip(chunks, vectors, strict=False):
        has_emb = vec is not None
        db.add(KBChunk(
            document_id=doc.id,
            department=doc.department,
            chunk_index=chunk.index,
            content=chunk.content,
            embedding=vec,
            embedding_provider=gateway.provider_name if has_emb else None,
            embedding_model=embedding_model if has_emb else None,
            embedding_dimensions=embedding_dims if has_emb else None,
            token_count=chunk.token_count,
            char_count=chunk.char_count,
            chunk_metadata=chunk.metadata,
        ))
        if has_emb:
            embedded += 1

    doc.total_chunks = len(chunks)
    doc.total_tokens = sum(c.token_count for c in chunks)
    await db.flush()

    return PipelineResult(
        document_id=doc.id,
        total_chunks=len(chunks),
        total_tokens=doc.total_tokens,
        embedded_chunks=embedded,
        format="reindex",
        success=True,
    )


async def cascade_delete_document(
    db: AsyncSession, document_id: uuid.UUID,
) -> bool:
    """문서 삭제 — 청크/메타데이터 cascade 정리."""
    doc = await db.get(KBDocument, document_id)
    if not doc:
        return False

    # KBChunk는 ondelete="CASCADE"로 자동 삭제되지만 명시적 삭제
    chunks = list((await db.execute(
        select(KBChunk).where(KBChunk.document_id == document_id)
    )).scalars().all())
    for c in chunks:
        await db.delete(c)

    await db.delete(doc)
    await db.flush()
    return True
