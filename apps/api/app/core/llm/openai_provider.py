"""OpenAI Provider — openai SDK 사용 (선택적).

`openai` 패키지가 설치되어 있고 `OPENAI_API_KEY`가 설정된 경우에만 사용 가능.
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


class OpenAIProvider(LLMProviderBase):
    """OpenAI Chat Completions API wrapper."""

    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_sec: float,
    ) -> None:
        if not api_key:
            raise LLMAuthError("OPENAI_API_KEY is empty")
        try:
            from openai import AsyncOpenAI  # type: ignore
        except ImportError as exc:
            raise LLMGatewayError(
                "`openai` 패키지가 설치되어 있지 않습니다. "
                "`pip install openai` 후 다시 시도하세요."
            ) from exc

        self.model = model
        self.timeout_sec = timeout_sec
        self._client = AsyncOpenAI(api_key=api_key, timeout=timeout_sec)

    async def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMGenerationResult:
        try:
            from openai import (  # type: ignore
                APIConnectionError,
                APIError,
                APITimeoutError,
                AuthenticationError,
                RateLimitError,
            )
        except ImportError as exc:
            raise LLMGatewayError("openai 패키지를 로드할 수 없습니다.") from exc

        try:
            resp = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except APITimeoutError as exc:
            raise LLMTimeoutError(str(exc)) from exc
        except RateLimitError as exc:
            raise LLMRateLimitError(str(exc)) from exc
        except AuthenticationError as exc:
            raise LLMAuthError(str(exc)) from exc
        except (APIConnectionError, APIError) as exc:
            raise LLMGatewayError(f"OpenAI API error: {exc}") from exc

        choice = resp.choices[0]
        usage = resp.usage

        return LLMGenerationResult(
            output_text=choice.message.content or "",
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            finish_reason=choice.finish_reason,
            model=resp.model,
            raw_response=resp.model_dump() if hasattr(resp, "model_dump") else None,
        )
