"""KB 하이브리드 검색 — 벡터 + 렉시컬 + RRF.

Day 9 설계
---------
1. **벡터 검색**: pgvector `embedding <=> query_vector` (cosine distance)
2. **렉시컬 검색**: `pg_trgm.similarity(content, query)` — 한국어도 n-gram 기반으로 동작
3. **결합 (RRF)**: Reciprocal Rank Fusion — 정규화 불필요, 강건한 순위 결합

   score(d) = Σ (1 / (k + rank_in_query_type(d)))

4. **리랭킹**: 선택적 후처리 단계 (reranker.py 참고)
5. **필터링**: department / review_status / tags / source_year

검색 대상은 기본적으로 **PUBLISHED 상태**의 청크만이며, 관리자/개발자는 모든 상태를 조회 가능.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field

from sqlalchemy import Float, Integer, String, and_, bindparam, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.embeddings import get_embedding_gateway
from app.models.enums import Department, KBReviewStatus
from app.models.kb_document import KBChunk, KBDocument

logger = logging.getLogger(__name__)


# === 상수 ===
RRF_K = 60  # 표준 RRF 상수 (Cormack et al., 2009)
DEFAULT_CANDIDATE_LIMIT = 50  # 각 검색 방식에서 가져올 후보 수
DEFAULT_TOP_K = 10


# === 자료구조 ===
@dataclass
class SearchHit:
    """검색 결과 1건."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    department: Department
    chunk_index: int
    content: str
    vector_score: float | None = None  # 0.0~1.0 (높을수록 유사)
    lexical_score: float | None = None  # 0.0~1.0
    rrf_score: float = 0.0  # 최종 결합 점수
    vector_rank: int | None = None
    lexical_rank: int | None = None
    source: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class SearchRequest:
    """검색 요청."""

    query: str
    department: Department | None = None
    tags: list[str] | None = None
    source_year: int | None = None
    include_review_statuses: tuple[KBReviewStatus, ...] = (KBReviewStatus.PUBLISHED,)
    top_k: int = DEFAULT_TOP_K
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT
    use_vector: bool = True
    use_lexical: bool = True


# === 내부 헬퍼 ===
def _build_filter_clauses(req: SearchRequest):
    """문서/청크 공통 필터 SQLAlchemy 절 리스트."""
    clauses = []
    if req.department is not None:
        clauses.append(KBChunk.department == req.department)
    if req.include_review_statuses:
        clauses.append(KBDocument.review_status.in_(req.include_review_statuses))
    if req.tags:
        clauses.append(KBDocument.tags.overlap(req.tags))
    if req.source_year is not None:
        clauses.append(KBDocument.source_year == req.source_year)
    return clauses


async def _vector_search(
    db: AsyncSession,
    req: SearchRequest,
    query_vector: list[float],
) -> list[tuple[int, SearchHit]]:
    """pgvector 코사인 거리 기반 상위 후보 검색.

    Returns
    -------
    list[(rank, SearchHit)]
        rank는 1-indexed.
    """
    if not req.use_vector:
        return []

    # cosine_distance: 0(동일) ~ 2(반대). 유사도는 1 - distance/2 로 변환 (0~1 범위).
    distance = KBChunk.embedding.cosine_distance(query_vector)
    similarity = (1.0 - distance / 2.0).label("vector_similarity")

    stmt = (
        select(
            KBChunk.id.label("chunk_id"),
            KBChunk.document_id,
            KBDocument.title.label("document_title"),
            KBChunk.department,
            KBChunk.chunk_index,
            KBChunk.content,
            KBDocument.source,
            KBDocument.tags,
            similarity,
        )
        .join(KBDocument, KBDocument.id == KBChunk.document_id)
        .where(KBChunk.embedding.is_not(None))
    )
    clauses = _build_filter_clauses(req)
    if clauses:
        stmt = stmt.where(and_(*clauses))

    stmt = stmt.order_by(distance.asc()).limit(req.candidate_limit)
    rows = (await db.execute(stmt)).all()

    out: list[tuple[int, SearchHit]] = []
    for rank, row in enumerate(rows, start=1):
        hit = SearchHit(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_title=row.document_title,
            department=row.department,
            chunk_index=row.chunk_index,
            content=row.content,
            vector_score=float(row.vector_similarity),
            vector_rank=rank,
            source=row.source,
            tags=list(row.tags) if row.tags else [],
        )
        out.append((rank, hit))
    return out


async def _lexical_search(
    db: AsyncSession,
    req: SearchRequest,
) -> list[tuple[int, SearchHit]]:
    """pg_trgm similarity 기반 렉시컬 검색.

    한국어도 n-gram(trigram) 기반이라 동작한다. 정확한 토큰 매칭은 아니지만
    공식 한글 형태소 분석기가 없는 환경에서의 baseline으로 적합.
    """
    if not req.use_lexical or not req.query.strip():
        return []

    # similarity(content, :query)를 사용. 0.0 ~ 1.0 (높을수록 유사)
    similarity = func.similarity(KBChunk.content, bindparam("q_text", req.query)).label(
        "lexical_similarity"
    )

    stmt = (
        select(
            KBChunk.id.label("chunk_id"),
            KBChunk.document_id,
            KBDocument.title.label("document_title"),
            KBChunk.department,
            KBChunk.chunk_index,
            KBChunk.content,
            KBDocument.source,
            KBDocument.tags,
            similarity,
        )
        .join(KBDocument, KBDocument.id == KBChunk.document_id)
    )
    clauses = _build_filter_clauses(req)
    # 아주 낮은 유사도는 컷오프 (0.0 초과만)
    clauses.append(similarity > 0.0)
    stmt = stmt.where(and_(*clauses))
    stmt = stmt.order_by(similarity.desc()).limit(req.candidate_limit)

    rows = (await db.execute(stmt)).all()
    out: list[tuple[int, SearchHit]] = []
    for rank, row in enumerate(rows, start=1):
        hit = SearchHit(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            document_title=row.document_title,
            department=row.department,
            chunk_index=row.chunk_index,
            content=row.content,
            lexical_score=float(row.lexical_similarity),
            lexical_rank=rank,
            source=row.source,
            tags=list(row.tags) if row.tags else [],
        )
        out.append((rank, hit))
    return out


def _fuse_rrf(
    vector_hits: list[tuple[int, SearchHit]],
    lexical_hits: list[tuple[int, SearchHit]],
) -> list[SearchHit]:
    """Reciprocal Rank Fusion으로 두 결과를 결합.

    같은 청크가 양쪽에 등장하면 rank의 역수를 합산한다.
    """
    merged: dict[uuid.UUID, SearchHit] = {}

    def _upsert(hit: SearchHit, rrf_contribution: float) -> None:
        existing = merged.get(hit.chunk_id)
        if existing is None:
            hit.rrf_score = rrf_contribution
            merged[hit.chunk_id] = hit
        else:
            existing.rrf_score += rrf_contribution
            # 점수 병합 (한쪽만 있던 점수를 채워줌)
            if existing.vector_score is None and hit.vector_score is not None:
                existing.vector_score = hit.vector_score
                existing.vector_rank = hit.vector_rank
            if existing.lexical_score is None and hit.lexical_score is not None:
                existing.lexical_score = hit.lexical_score
                existing.lexical_rank = hit.lexical_rank

    for rank, hit in vector_hits:
        _upsert(hit, 1.0 / (RRF_K + rank))

    for rank, hit in lexical_hits:
        # lexical_hits는 별도 인스턴스이므로 merged에 새로 upsert
        _upsert(hit, 1.0 / (RRF_K + rank))

    fused = list(merged.values())
    fused.sort(key=lambda h: h.rrf_score, reverse=True)
    return fused


# === Public API ===
async def search(db: AsyncSession, req: SearchRequest) -> list[SearchHit]:
    """하이브리드 KB 검색.

    1. 쿼리를 임베딩
    2. 병렬(논리적으로) 벡터 + 렉시컬 후보 수집
    3. RRF로 결합
    4. Top-K 반환 (리랭킹은 호출자에서 선택적으로 수행)
    """
    query = req.query.strip()
    if not query:
        return []

    # 1) 쿼리 임베딩
    query_vector: list[float] | None = None
    if req.use_vector:
        try:
            gateway = get_embedding_gateway()
            result = await gateway.embed_batch([query])
            if result.vectors:
                query_vector = result.vectors[0]
        except Exception as exc:  # noqa: BLE001
            logger.exception("Query embedding failed, falling back to lexical-only: %s", exc)
            query_vector = None

    # 2) 각 검색 방식 실행
    vector_hits: list[tuple[int, SearchHit]] = []
    lexical_hits: list[tuple[int, SearchHit]] = []

    if query_vector is not None:
        vector_hits = await _vector_search(db, req, query_vector)
    lexical_hits = await _lexical_search(db, req)

    # 3) RRF 결합
    fused = _fuse_rrf(vector_hits, lexical_hits)

    # 4) Top-K
    return fused[: max(1, req.top_k)]
