"""EmbeddingGateway — provider 선택 + 배치 분할 + 재시도.

LLM Gateway와 동일한 fallback 패턴:
- 환경 변수 `EMBEDDING_PROVIDER=openai` + `OPENAI_API_KEY` 있으면 OpenAI
- 그 외에는 Mock provider (결정론적, API 키 불필요)
"""

from __future__ import annotations

import logging
from functools import lru_cache

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.core.embeddings.base import (
    EmbeddingAuthError,
    EmbeddingError,
    EmbeddingProviderBase,
    EmbeddingRateLimitError,
    EmbeddingResult,
    EmbeddingTimeoutError,
)
from app.core.embeddings.mock_provider import MockEmbeddingProvider
from app.models.enums import EmbeddingProvider

logger = logging.getLogger(__name__)


def _build_provider() -> tuple[EmbeddingProviderBase, EmbeddingProvider]:
    """환경 변수에 따라 임베딩 provider 선택. 실패 시 Mock으로 fallback."""
    requested = (settings.embedding_provider or "mock").lower()

    if requested == "openai":
        try:
            from app.core.embeddings.openai_provider import OpenAIEmbeddingProvider

            provider = OpenAIEmbeddingProvider(
                api_key=settings.openai_api_key,
                model=settings.embedding_model,
                dimensions=settings.embedding_dimensions,
                timeout_sec=settings.llm_timeout_sec,
            )
            logger.info(
                "Embedding Gateway: openai (model=%s dims=%d)",
                settings.embedding_model,
                settings.embedding_dimensions,
            )
            return provider, EmbeddingProvider.OPENAI
        except (EmbeddingAuthError, EmbeddingError) as exc:
            logger.warning(
                "OpenAI embedding unavailable, falling back to mock: %s", exc
            )

    logger.info(
        "Embedding Gateway: mock (dims=%d)", settings.embedding_dimensions
    )
    return (
        MockEmbeddingProvider(dimensions=settings.embedding_dimensions),
        EmbeddingProvider.MOCK,
    )


class EmbeddingGateway:
    """프로젝트 전역 단일 임베딩 진입점."""

    def __init__(self) -> None:
        self._provider, self._provider_enum = _build_provider()

    @property
    def provider_name(self) -> EmbeddingProvider:
        return self._provider_enum

    @property
    def model(self) -> str:
        return self._provider.model

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """배치 임베딩 + 자동 분할 + 재시도."""
        if not texts:
            return EmbeddingResult(
                vectors=[],
                model=self.model,
                dimensions=self.dimensions,
                total_tokens=0,
            )

        max_batch = max(1, settings.embedding_batch_size)

        @retry(
            reraise=True,
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(
                (EmbeddingTimeoutError, EmbeddingRateLimitError, EmbeddingError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        async def _call(chunk: list[str]) -> EmbeddingResult:
            return await self._provider.embed_batch(chunk)

        all_vectors: list[list[float]] = []
        total_tokens = 0
        model = self.model
        for i in range(0, len(texts), max_batch):
            chunk = texts[i : i + max_batch]
            result = await _call(chunk)
            all_vectors.extend(result.vectors)
            total_tokens += result.total_tokens
            model = result.model

        return EmbeddingResult(
            vectors=all_vectors,
            model=model,
            dimensions=self.dimensions,
            total_tokens=total_tokens,
        )


@lru_cache
def get_embedding_gateway() -> EmbeddingGateway:
    return EmbeddingGateway()
