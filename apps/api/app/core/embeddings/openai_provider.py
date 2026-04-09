"""OpenAI Embedding Provider — text-embedding-3-small/large.

lazy import로 `openai` SDK가 설치되지 않은 환경에서도 모듈 로드 자체는 실패하지 않게 한다.
`text-embedding-3-large`의 경우 `dimensions=1536` 파라미터를 활용해 pgvector
HNSW 인덱스 제한(<=2000)에 맞춘다.
"""

from __future__ import annotations

import logging

from app.core.embeddings.base import (
    EmbeddingAuthError,
    EmbeddingError,
    EmbeddingProviderBase,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingTimeoutError,
)

logger = logging.getLogger(__name__)


class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    """OpenAI Embeddings API wrapper."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_sec: float,
    ) -> None:
        if not api_key:
            raise EmbeddingAuthError("OPENAI_API_KEY is empty")
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise EmbeddingError(
                "`openai` 패키지가 설치되어 있지 않습니다. "
                "`pip install openai` 후 다시 시도하세요."
            ) from exc

        self._model = model
        self._dimensions = dimensions
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_sec)

    @property
    def model(self) -> str:
        return self._model

    @property
    def dimensions(self) -> int:
        return self._dimensions

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        if not texts:
            return EmbeddingResult(
                vectors=[], model=self._model, dimensions=self._dimensions, total_tokens=0
            )

        try:
            from openai import (  # type: ignore
                APIConnectionError,
                APIError,
                APITimeoutError,
                AuthenticationError,
                RateLimitError,
            )
        except ImportError as exc:
            raise EmbeddingError("openai 패키지를 로드할 수 없습니다.") from exc

        # text-embedding-3-* 모델은 `dimensions` 파라미터를 지원.
        # 레거시 ada-002 등은 dimensions 파라미터가 없으므로 안전하게 분기.
        kwargs: dict = {"model": self._model, "input": texts}
        if self._model.startswith("text-embedding-3"):
            kwargs["dimensions"] = self._dimensions

        try:
            resp = await self._client.embeddings.create(**kwargs)
        except APITimeoutError as exc:
            raise EmbeddingTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise EmbeddingRateLimitError(str(exc)) from exc
        except AuthenticationError as exc:
            raise EmbeddingAuthError(str(exc)) from exc
        except (APIConnectionError, APIError) as exc:
            raise EmbeddingError(f"OpenAI embedding API error: {exc}") from exc

        vectors = [item.embedding for item in resp.data]
        # 안전성 검증 — 모든 벡터의 차원이 일치해야 함
        if vectors and len(vectors[0]) != self._dimensions:
            logger.warning(
                "OpenAI returned dimensions=%d, expected %d",
                len(vectors[0]),
                self._dimensions,
            )
        return EmbeddingResult(
            vectors=vectors,
            model=resp.model,
            dimensions=self._dimensions,
            total_tokens=resp.usage.total_tokens if resp.usage else 0,
        )
