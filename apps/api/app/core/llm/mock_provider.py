"""Mock LLM Provider — API 키 없이 개발/테스트할 때 사용.

결정론적이고 안전한 응답을 반환한다. 실제 LLM이 없을 때 fallback으로 자동 선택된다.
"""

from __future__ import annotations

import asyncio
import hashlib

from app.core.llm.base import LLMGenerationResult, LLMProviderBase


class MockProvider(LLMProviderBase):
    """결정론적 mock 응답."""

    name = "mock"

    def __init__(self, model: str = "mock-llm-v1") -> None:
        self.model = model

    async def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int,
        temperature: float,
    ) -> LLMGenerationResult:
        # 약간의 비동기 지연을 흉내내어 latency 측정 코드 경로를 검증
        await asyncio.sleep(0.01)

        # 결정론적이지만 입력에 따라 달라지는 응답
        digest = hashlib.sha1(
            (system + "||" + user).encode("utf-8")
        ).hexdigest()[:8]
        snippet = user[:200].replace("\n", " ")

        body = (
            f"[MOCK LLM 응답] (digest={digest})\n"
            f"실제 LLM이 연결되어 있지 않아 mock provider가 응답합니다.\n\n"
            f"질문 요약: {snippet}\n\n"
            f"이 응답은 환경 변수 LLM_PROVIDER, ANTHROPIC_API_KEY 또는 "
            f"OPENAI_API_KEY를 설정하면 실제 LLM 응답으로 대체됩니다."
        )

        # 토큰은 단어 수 기반으로 근사
        return LLMGenerationResult(
            output_text=body,
            input_tokens=len((system + user).split()),
            output_tokens=len(body.split()),
            finish_reason="stop",
            model=self.model,
            raw_response={"mock": True, "digest": digest},
        )
