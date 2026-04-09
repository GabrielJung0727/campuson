"""LLMGateway — provider 선택 + 재시도 + 통합 인터페이스.

설계 원칙
--------
1. 환경 변수 `LLM_PROVIDER`로 anthropic / openai / mock 중 선택
2. API 키가 비어있거나 SDK가 미설치면 자동으로 mock으로 fallback (개발 친화)
3. 실패 시 tenacity로 지수 백오프 재시도 (rate limit / connection 오류만)
4. 인증 오류는 재시도하지 않음 (즉시 fail)
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
from app.core.llm.base import (
    LLMAuthError,
    LLMGatewayError,
    LLMGenerationResult,
    LLMProviderBase,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.core.llm.mock_provider import MockProvider
from app.models.enums import LLMProvider

logger = logging.getLogger(__name__)


def _build_provider() -> tuple[LLMProviderBase, LLMProvider]:
    """환경 변수에 따라 적절한 provider를 만들고, 실패하면 Mock으로 fallback.

    Returns
    -------
    (provider, enum)
    """
    requested = (settings.llm_provider or "mock").lower()

    if requested == "anthropic":
        try:
            from app.core.llm.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider(
                api_key=settings.anthropic_api_key,
                model=settings.llm_model,
                timeout_sec=settings.llm_timeout_sec,
            )
            logger.info("LLM Gateway: anthropic provider initialized (model=%s)", settings.llm_model)
            return provider, LLMProvider.ANTHROPIC
        except (LLMAuthError, LLMGatewayError) as exc:
            logger.warning("Anthropic provider unavailable, falling back to mock: %s", exc)

    if requested == "openai":
        try:
            from app.core.llm.openai_provider import OpenAIProvider

            provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
                timeout_sec=settings.llm_timeout_sec,
            )
            logger.info("LLM Gateway: openai provider initialized (model=%s)", settings.openai_model)
            return provider, LLMProvider.OPENAI
        except (LLMAuthError, LLMGatewayError) as exc:
            logger.warning("OpenAI provider unavailable, falling back to mock: %s", exc)

    logger.info("LLM Gateway: using mock provider")
    return MockProvider(), LLMProvider.MOCK


class LLMGateway:
    """프로젝트 전역에서 사용하는 단일 LLM 진입점."""

    def __init__(self) -> None:
        self._provider, self._provider_enum = _build_provider()

    @property
    def provider_name(self) -> LLMProvider:
        return self._provider_enum

    @property
    def model(self) -> str:
        return getattr(self._provider, "model", settings.llm_model)

    async def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> LLMGenerationResult:
        """단일 응답 생성 + 재시도."""
        max_tokens = max_tokens or settings.llm_max_tokens
        temperature = (
            temperature if temperature is not None else settings.llm_temperature
        )

        @retry(
            reraise=True,
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(
                (LLMTimeoutError, LLMRateLimitError, LLMGatewayError)
            ),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        )
        async def _call() -> LLMGenerationResult:
            return await self._provider.generate(
                system=system,
                user=user,
                max_tokens=max_tokens,
                temperature=temperature,
            )

        return await _call()


@lru_cache
def get_llm_gateway() -> LLMGateway:
    """싱글톤 LLM Gateway."""
    return LLMGateway()
