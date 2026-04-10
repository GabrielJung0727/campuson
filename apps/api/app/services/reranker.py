"""Top-K 리랭커 — 룰 베이스 + cross-encoder placeholder.

Day 9 설계
---------
- **Stage 1**: kb_search_service가 RRF로 10~30 후보를 뽑음
- **Stage 2 (리랭커)**: 이 모듈이 후보들을 다시 정렬

Day 9는 **룰 베이스 리랭커**를 기본으로 사용한다:
- 쿼리 토큰의 완전 매칭 비중 (정확도)
- 쿼리 단어가 문서 초반(첫 200자)에 나오는지 (두괄식 가중)
- 너무 짧거나 너무 긴 청크 페널티
- RRF 점수를 기본 prior로 사용

**Cross-encoder**는 향후 Day 10+에서 sentence-transformers의
`bongsoo/kpf-cross-encoder-v1` 같은 한국어 모델로 교체 가능하며,
현재는 `CrossEncoderRerankerPlaceholder` 클래스로 인터페이스만 남겨둔다.

모델 로딩은 무거우므로 lazy + 옵션이어야 하며 임포트 자체는 실패하지 않아야 한다.
"""

from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.kb_search_service import SearchHit

logger = logging.getLogger(__name__)

# === 튜닝 상수 ===
MIN_CHUNK_TOKENS = 80  # 이보다 짧은 청크는 약간 페널티
MAX_CHUNK_TOKENS = 2000
LEAD_TEXT_LENGTH = 200
EXACT_MATCH_BONUS = 0.4
LEAD_MATCH_BONUS = 0.2
LENGTH_PENALTY = -0.1
RRF_WEIGHT = 1.0


@dataclass
class RerankResult:
    """리랭킹 결과 (SearchHit 확장)."""

    hit: SearchHit
    rerank_score: float
    signals: dict[str, float]  # 어떤 신호가 기여했는지 디버그용


class RerankerBase(ABC):
    """리랭커 공통 인터페이스."""

    name: str = "base"

    @abstractmethod
    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[RerankResult]:
        ...


class RuleBasedReranker(RerankerBase):
    """룰 베이스 리랭커 — 쿼리 매칭 / 위치 / 길이 페널티."""

    name = "rule-based-v1"

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """단순 토크나이저. 한국어는 whitespace + 2-gram 보조."""
        base = [t.lower() for t in re.findall(r"[\w가-힣]+", text or "") if len(t) >= 2]
        return base

    def _score_hit(self, query_tokens: set[str], hit: SearchHit) -> tuple[float, dict[str, float]]:
        content = hit.content or ""
        content_lower = content.lower()
        signals: dict[str, float] = {}

        # 1) Prior: RRF 점수
        prior = hit.rrf_score * RRF_WEIGHT
        signals["rrf_prior"] = prior

        # 2) Exact match 비중
        if query_tokens:
            matched = sum(1 for t in query_tokens if t in content_lower)
            match_ratio = matched / len(query_tokens)
            exact_bonus = match_ratio * EXACT_MATCH_BONUS
            signals["exact_match"] = exact_bonus
        else:
            exact_bonus = 0.0

        # 3) Lead text match (두괄식 가중)
        lead_text = content_lower[:LEAD_TEXT_LENGTH]
        lead_matched = sum(1 for t in query_tokens if t in lead_text) if query_tokens else 0
        lead_bonus = (lead_matched / max(1, len(query_tokens))) * LEAD_MATCH_BONUS if query_tokens else 0.0
        signals["lead_match"] = lead_bonus

        # 4) Length penalty — 너무 짧은 청크는 신뢰도 감소
        approx_tokens = len(content) // 2  # 한글 글자당 ~0.5 토큰 근사
        if approx_tokens < MIN_CHUNK_TOKENS:
            length_signal = LENGTH_PENALTY
        elif approx_tokens > MAX_CHUNK_TOKENS:
            length_signal = LENGTH_PENALTY * 0.5
        else:
            length_signal = 0.0
        signals["length"] = length_signal

        total = prior + exact_bonus + lead_bonus + length_signal
        return total, signals

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[RerankResult]:
        tokens = set(self._tokenize(query))
        results = []
        for hit in hits:
            score, signals = self._score_hit(tokens, hit)
            results.append(RerankResult(hit=hit, rerank_score=score, signals=signals))
        results.sort(key=lambda r: r.rerank_score, reverse=True)
        return results[: max(1, top_k)]


class CrossEncoderRerankerPlaceholder(RerankerBase):
    """Cross-encoder 리랭커 placeholder.

    실제 구현은 `sentence-transformers` 설치 후 Day 10+ 에서 활성화한다.
    예시:

    ```python
    from sentence_transformers import CrossEncoder
    model = CrossEncoder("bongsoo/kpf-cross-encoder-v1")
    scores = model.predict([(query, h.content) for h in hits])
    ```

    현재는 rule-based 리랭커로 fallback한다.
    """

    name = "cross-encoder-placeholder"

    def __init__(self) -> None:
        self._fallback = RuleBasedReranker()
        self._ce_model = None  # Day 10+에서 교체

    def rerank(self, query: str, hits: list[SearchHit], top_k: int) -> list[RerankResult]:
        logger.debug("CrossEncoderRerankerPlaceholder → rule-based fallback")
        return self._fallback.rerank(query, hits, top_k)


# === Factory ===
_default_reranker: RerankerBase | None = None


def get_reranker() -> RerankerBase:
    """프로세스 단위 싱글톤 리랭커. Day 9 기본은 rule-based."""
    global _default_reranker
    if _default_reranker is None:
        _default_reranker = RuleBasedReranker()
    return _default_reranker
