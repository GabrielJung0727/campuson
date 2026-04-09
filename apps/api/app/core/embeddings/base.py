"""임베딩 Provider 추상 클래스 + 공통 자료구조."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class EmbeddingError(Exception):
    """임베딩 호출 관련 베이스 예외."""

    pass


class EmbeddingAuthError(EmbeddingError):
    pass


class EmbeddingRateLimitError(EmbeddingError):
    pass


class EmbeddingTimeoutError(EmbeddingError):
    pass


@dataclass
class EmbeddingResult:
    """배치 임베딩 호출의 결과."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    total_tokens: int


class EmbeddingProviderBase(ABC):
    """임베딩 Provider 공통 인터페이스."""

    name: str = "base"

    @property
    @abstractmethod
    def model(self) -> str: ...

    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> EmbeddingResult:
        """텍스트 목록을 배치로 임베딩.

        구현체는 입력 길이 제한, rate limit, 재시도 등을 고려해야 한다.
        """
        ...
