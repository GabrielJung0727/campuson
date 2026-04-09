"""Anthropic Claude Provider — anthropic SDK 사용.

`anthropic` 패키지가 설치되어 있고 `ANTHROPIC_API_KEY`가 설정된 경우에만 사용 가능.
import는 lazy로 처리해 패키지 미설치 환경에서도 모듈 로드 자체는 실패하지 않게 한다.
"""

from __future__ import annotations

import logging

from app.core.llm.base import (
    LLMAuthError,
    LLMGatewayError,
    LLMGenerationResult,
    LLMProviderBase,
    LLMRateLimitError,
    LLMTimeoutError,
)

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProviderBase):
    """Anthropic Messages API wrapper."""

    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_sec: float,
    ) -> None:
        if not api_key:
            raise LLMAuthError("ANTHROPIC_API_KEY is empty")

        try:
            from anthropic import AsyncAnthropic  # type: ignore
        except ImportError as exc:
            raise LLMGatewayError(
                "`anthropic` 패키지가 설치되어 있지 않습니다. "
                "`pip install anthropic` 후 다시 시도하세요."
            ) from exc

        self.model = model
        self.timeout_sec = timeout_sec
        self._client = AsyncAnthropic(api_key=api_key, timeout=timeout_sec)

    async def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMGenerationResult:
        try:
            from anthropic import (  # type: ignore
                APIConnectionError,
                APIStatusError,
                APITimeoutError,
                AuthenticationError,
                RateLimitError,
            )
        except ImportError as exc:
            raise LLMGatewayError("anthropic 패키지를 로드할 수 없습니다.") from exc

        try:
            msg = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except (APIConnectionError, APIStatusError) as exc:
            raise LLMGatewayError(f"Anthropic API error: {exc}") from exc

        # 응답 텍스트 추출
        text_blocks = [
            getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text"
        ]
        output_text = "".join(text_blocks)

        return LLMGenerationResult(
            output_text=output_text,
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
            finish_reason=msg.stop_reason,
            model=msg.model,
            raw_response=msg.model_dump() if hasattr(msg, "model_dump") else None,
        )
