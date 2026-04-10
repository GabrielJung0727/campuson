"""KB (지식베이스) 라우터.

엔드포인트
---------
- POST /kb/search              — 하이브리드 검색 (학생 포함 모든 인증 사용자)
- POST /kb/documents           — 문서 적재 (ADMIN/DEVELOPER)
- GET  /kb/documents           — 문서 목록 (인증 사용자)
- GET  /kb/documents/{id}      — 문서 단건 (인증 사용자)
- POST /kb/documents/{id}/review — 검수 승인 (PROFESSOR/ADMIN/DEV)
- DELETE /kb/documents/{id}    — 문서 삭제 (ADMIN/DEV)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    require_roles,
)
from app.db.session import get_db
from app.models.enums import Department, KBReviewStatus, Role
from app.models.kb_document import KBDocument
from app.models.user import User
from app.schemas.common import MessageResponse
from app.schemas.kb import (
    KBDocumentListResponse,
    KBDocumentResponse,
    KBIngestRequest,
    KBIngestResponse,
    KBReviewRequest,
    KBSearchHit,
    KBSearchRequest,
    KBSearchResponse,
)
from app.services.kb_ingest_service import (
    DocumentNotFoundError,
    IngestRequest,
    KBIngestError,
    delete_document,
    get_document,
    ingest_document,
    mark_reviewed,
)
from app.services.kb_search_service import (
    SearchRequest,
    search,
)
from app.services.reranker import get_reranker

router = APIRouter(prefix="/kb", tags=["kb"])


# ===== 적재 =====
@router.post(
    "/documents",
    response_model=KBIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="KB 문서 적재 (관리자/개발자 전용)",
)
async def ingest_endpoint(
    payload: KBIngestRequest,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> KBIngestResponse:
    try:
        result = await ingest_document(
            db,
            IngestRequest(
                department=payload.department,
                title=payload.title,
                content=payload.content,
                source=payload.source,
                source_url=payload.source_url,
                source_year=payload.source_year,
                tags=payload.tags,
                extra_metadata=payload.extra_metadata,
                review_status=payload.review_status,
            ),
        )
    except KBIngestError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return KBIngestResponse(
        document_id=result.document_id,
        total_chunks=result.total_chunks,
        total_tokens=result.total_tokens,
        embedded_chunks=result.embedded_chunks,
        embedding_model=result.embedding_model,
        embedding_dimensions=result.embedding_dimensions,
    )


# ===== 목록 / 단건 =====
@router.get(
    "/documents",
    response_model=KBDocumentListResponse,
    summary="KB 문서 목록 조회",
)
async def list_documents_endpoint(
    department: Department | None = Query(default=None),
    review_status: KBReviewStatus | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KBDocumentListResponse:
    base = select(KBDocument)
    if department:
        base = base.where(KBDocument.department == department)
    if review_status:
        base = base.where(KBDocument.review_status == review_status)
    base = base.order_by(KBDocument.created_at.desc())

    # total
    count_stmt = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # items
    items_stmt = base.offset(offset).limit(limit)
    rows = list((await db.execute(items_stmt)).scalars().all())
    return KBDocumentListResponse(
        items=[KBDocumentResponse.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/documents/{document_id}",
    response_model=KBDocumentResponse,
    summary="KB 문서 단건 조회",
)
async def get_document_endpoint(
    document_id: uuid.UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KBDocumentResponse:
    try:
        doc = await get_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KBDocumentResponse.model_validate(doc)


# ===== 검수 =====
@router.post(
    "/documents/{document_id}/review",
    response_model=KBDocumentResponse,
    summary="KB 문서 검수 승인 (PROFESSOR/ADMIN/DEV)",
)
async def review_document(
    document_id: uuid.UUID,
    payload: KBReviewRequest,
    current_user: User = Depends(
        require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> KBDocumentResponse:
    try:
        doc = await mark_reviewed(db, document_id, current_user.id, publish=payload.publish)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return KBDocumentResponse.model_validate(doc)


# ===== 삭제 =====
@router.delete(
    "/documents/{document_id}",
    response_model=MessageResponse,
    summary="KB 문서 삭제 (ADMIN/DEV)",
)
async def delete_document_endpoint(
    document_id: uuid.UUID,
    _user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    try:
        await delete_document(db, document_id)
    except DocumentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return MessageResponse(message=f"Document {document_id} deleted")


# ===== 검색 =====
@router.post(
    "/search",
    response_model=KBSearchResponse,
    summary="하이브리드 KB 검색 (벡터 + 렉시컬 + RRF + 리랭킹)",
)
async def search_endpoint(
    payload: KBSearchRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> KBSearchResponse:
    # 기본은 PUBLISHED만. 관리자/개발자는 include_unpublished=true 가능.
    if payload.include_unpublished:
        if current_user.role not in (Role.ADMIN, Role.DEVELOPER, Role.PROFESSOR):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="include_unpublished requires PROFESSOR or higher",
            )
        statuses = (
            KBReviewStatus.DRAFT,
            KBReviewStatus.REVIEWED,
            KBReviewStatus.PUBLISHED,
        )
    else:
        statuses = (KBReviewStatus.PUBLISHED,)

    req = SearchRequest(
        query=payload.query,
        department=payload.department,
        tags=payload.tags,
        source_year=payload.source_year,
        include_review_statuses=statuses,
        top_k=payload.top_k,
        candidate_limit=payload.candidate_limit,
        use_vector=payload.use_vector,
        use_lexical=payload.use_lexical,
    )
    hits = await search(db, req)

    # Stage 2: 리랭킹
    reranked = payload.rerank and bool(hits)
    reranker_name: str | None = None
    if reranked:
        reranker = get_reranker()
        reranker_name = reranker.name
        reranked_results = reranker.rerank(payload.query, hits, payload.top_k)
        response_hits = [
            KBSearchHit(
                chunk_id=r.hit.chunk_id,
                document_id=r.hit.document_id,
                document_title=r.hit.document_title,
                department=r.hit.department,
                chunk_index=r.hit.chunk_index,
                content=r.hit.content,
                source=r.hit.source,
                tags=r.hit.tags,
                vector_score=r.hit.vector_score,
                lexical_score=r.hit.lexical_score,
                vector_rank=r.hit.vector_rank,
                lexical_rank=r.hit.lexical_rank,
                rrf_score=r.hit.rrf_score,
                rerank_score=r.rerank_score,
                rerank_signals=r.signals,
            )
            for r in reranked_results
        ]
    else:
        response_hits = [
            KBSearchHit(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                document_title=h.document_title,
                department=h.department,
                chunk_index=h.chunk_index,
                content=h.content,
                source=h.source,
                tags=h.tags,
                vector_score=h.vector_score,
                lexical_score=h.lexical_score,
                vector_rank=h.vector_rank,
                lexical_rank=h.lexical_rank,
                rrf_score=h.rrf_score,
            )
            for h in hits
        ]

    return KBSearchResponse(
        query=payload.query,
        total=len(response_hits),
        reranked=reranked,
        reranker_name=reranker_name,
        hits=response_hits,
    )
