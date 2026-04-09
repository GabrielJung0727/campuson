"""LLM Provider 추상 클래스 + 공통 자료구조."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LLMGatewayError(Exception):
    """LLM 호출 관련 모든 예외의 베이스."""

    pass


class LLMTimeoutError(LLMGatewayError):
    pass


class LLMRateLimitError(LLMGatewayError):
    pass


class LLMAuthError(LLMGatewayError):
    pass


@dataclass
class LLMGenerationResult:
    """LLM 호출 결과 — service 레이어에서 사용."""

    output_text: str
    input_tokens: int
    output_tokens: int
    finish_reason: str | None
    model: str
    raw_response: dict | None = None


class LLMProviderBase(ABC):
    """모든 LLM Provider의 공통 인터페이스."""

    name: str = "base"

    @abstractmethod
    async def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMGenerationResult:
        """단일 응답 생성 (비스트리밍).

        구현체는 다음 예외 중 하나를 던질 수 있다:
        - LLMTimeoutError
        - LLMRateLimitError
        - LLMAuthError
        - LLMGatewayError (그 외)
        """
        ...
