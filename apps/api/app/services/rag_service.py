"""RAG (Retrieval-Augmented Generation) 서비스.

Day 10 설계
----------
1. 쿼리 → KB 하이브리드 검색 → 상위 K개 청크
2. 리랭킹 (rule-based)
3. 청크들을 컨텍스트 블록으로 포맷팅
4. 학생 프로파일(level, 취약영역)을 프롬프트에 주입
5. LLM 호출
6. 응답 + 인용(citation) 정보 반환

인용 포맷
--------
각 컨텍스트 조각을 [1], [2], ... 번호로 참조.
LLM에게 "답변에서 참조할 때 [숫자] 형태로 표기" 지시.
응답 후 실제 사용된 번호를 파싱하여 citation 메타데이터에 담는다.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_profile import AIProfile
from app.models.enums import Department, KBReviewStatus, Level
from app.services.kb_search_service import SearchHit, SearchRequest, search
from app.services.reranker import get_reranker

logger = logging.getLogger(__name__)


DEFAULT_TOP_K = 5
MAX_CONTEXT_CHARS = 3000  # 너무 길면 LLM context 낭비


@dataclass
class Citation:
    """답변 내 인용 1건."""

    number: int
    chunk_id: str
    document_id: str
    document_title: str
    source: str | None
    snippet: str  # 짧은 미리보기 (120자)


@dataclass
class RAGContext:
    """LLM에 주입될 RAG 컨텍스트."""

    formatted_text: str  # "[1] ...\n\n[2] ..." 형태
    citations: list[Citation]
    raw_hits: list[SearchHit]
    query: str


@dataclass
class StudentContext:
    """학생 개인화 컨텍스트."""

    level: Level | None = None
    department: Department | None = None
    weak_priority: list[dict] = field(default_factory=list)
    explanation_pref: str | None = None


# === 학생 프로파일 조회 ===
async def load_student_context(
    db: AsyncSession,
    user_id,
    department: Department | None = None,
) -> StudentContext:
    """AIProfile에서 학생 컨텍스트를 조회. 없으면 department만 설정."""
    from sqlalchemy import select

    profile = await db.scalar(select(AIProfile).where(AIProfile.user_id == user_id))
    if profile is None:
        return StudentContext(department=department)
    return StudentContext(
        level=profile.level,
        department=department,
        weak_priority=profile.weak_priority or [],
        explanation_pref=profile.explanation_pref.value
        if profile.explanation_pref
        else None,
    )


# === RAG 검색 + 포맷팅 ===
async def retrieve(
    db: AsyncSession,
    query: str,
    *,
    department: Department | None = None,
    top_k: int = DEFAULT_TOP_K,
    include_unpublished: bool = False,
) -> RAGContext:
    """쿼리로 KB를 검색하고 LLM context 포맷으로 반환."""
    # v0.5: 교수 승인(PUBLISHED) 문서 최우선 — 학생 RAG에서는 PUBLISHED만 기본 사용
    statuses = (
        (
            KBReviewStatus.DRAFT,
            KBReviewStatus.REVIEWED,
            KBReviewStatus.PUBLISHED,
        )
        if include_unpublished
        else (KBReviewStatus.PUBLISHED,)
    )

    req = SearchRequest(
        query=query,
        department=department,
        include_review_statuses=statuses,
        top_k=top_k * 2,  # 리랭킹 여유
        candidate_limit=30,
    )
    raw_hits = await search(db, req)
    if not raw_hits:
        return RAGContext(formatted_text="", citations=[], raw_hits=[], query=query)

    # 리랭킹
    reranker = get_reranker()
    reranked = reranker.rerank(query, raw_hits, top_k)
    hits = [r.hit for r in reranked]

    # 포맷팅
    blocks: list[str] = []
    citations: list[Citation] = []
    total_chars = 0
    for i, h in enumerate(hits, start=1):
        snippet_full = h.content.strip()
        # 너무 긴 청크는 잘라서 토큰 절약
        remaining = MAX_CONTEXT_CHARS - total_chars
        if remaining <= 200:
            break
        clip = snippet_full[: min(len(snippet_full), remaining)]
        block = f"[{i}] {h.document_title}\n{clip}"
        blocks.append(block)
        total_chars += len(block)

        citations.append(
            Citation(
                number=i,
                chunk_id=str(h.chunk_id),
                document_id=str(h.document_id),
                document_title=h.document_title,
                source=h.source,
                snippet=snippet_full[:120].replace("\n", " "),
            )
        )

    formatted = "\n\n".join(blocks)
    return RAGContext(formatted_text=formatted, citations=citations, raw_hits=hits, query=query)


# === 인용 파싱 ===
_CITATION_RE = re.compile(r"\[(\d+)\]")


def extract_used_citations(output_text: str, all_citations: list[Citation]) -> list[Citation]:
    """LLM 응답에서 실제 사용된 [숫자]를 추출해 해당 citation 반환."""
    if not output_text:
        return []
    used_numbers = set()
    for match in _CITATION_RE.finditer(output_text):
        try:
            used_numbers.add(int(match.group(1)))
        except ValueError:
            continue
    return [c for c in all_citations if c.number in used_numbers]


# === 프롬프트용 학생 컨텍스트 포맷 ===
def format_student_context_block(ctx: StudentContext) -> str:
    """프롬프트에 주입할 학생 컨텍스트 블록."""
    parts = []
    if ctx.level:
        parts.append(f"- 학습 수준: {ctx.level.value}")
    if ctx.explanation_pref:
        parts.append(f"- 선호 설명 난이도: {ctx.explanation_pref}")
    if ctx.weak_priority:
        weak_summary = ", ".join(
            f"{w.get('subject', '?')}/{w.get('unit', '')}".strip("/")
            for w in ctx.weak_priority[:3]
        )
        parts.append(f"- 취약 영역(우선순위 상위): {weak_summary}")
    if not parts:
        return ""
    return "## 학생 컨텍스트\n" + "\n".join(parts)
