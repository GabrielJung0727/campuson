"""Mock Embedding Provider — API 키 없이 개발/테스트.

결정론적 해시 기반 벡터를 생성한다. 같은 텍스트는 항상 같은 벡터.
유사한 텍스트는 일부 겹치는 토큰 해시로 약간의 유사성을 가진다.
"""

from __future__ import annotations

import hashlib
import math

from app.core.embeddings.base import EmbeddingProviderBase, EmbeddingResult


class MockEmbeddingProvider(EmbeddingProviderBase):
    """결정론적 pseudo-임베딩."""

    name = "mock"

    def __init__(self, dimensions: int, model: str = "mock-embedding-v1") -> None:
        self._dimensions = dimensions
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def _embed_one(self, text: str) -> list[float]:
        """단일 텍스트 → 고정 차원 벡터.

        간단한 결정론적 해시 기반 접근. 단어 별 해시를 dims 위치에 누적.
        """
        vec = [0.0] * self._dimensions
        for token in text.split():
            h = int.from_bytes(
                hashlib.sha1(token.encode("utf-8")).digest()[:8], "big", signed=False
            )
            idx = h % self._dimensions
            # 해시 상위 비트에서 +- 부호 결정
            sign = 1.0 if (h & 1) == 0 else -1.0
            vec[idx] += sign
        # L2 정규화 (코사인 유사도용)
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[], model=self._model, dimensions=self._dimensions, total_tokens=0
            )
        vectors = [self._embed_one(t) for t in texts]
        total_tokens = sum(len(t.split()) for t in texts)
        return EmbeddingResult(
            vectors=vectors,
            model=self._model,
            dimensions=self._dimensions,
            total_tokens=total_tokens,
        )
