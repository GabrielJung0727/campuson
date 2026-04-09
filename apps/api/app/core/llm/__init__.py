"""LLM Gateway 패키지.

Provider 추상화 + 재시도 + 타임아웃 + Mock fallback.

사용 예
-------
```python
from app.core.llm import get_llm_gateway

gateway = get_llm_gateway()
result = await gateway.generate(
    system="당신은 간호학 튜터입니다.",
    user="심방세동의 정의를 한 줄로 설명하세요.",
)
print(result.output_text, result.input_tokens, result.output_tokens)
```
"""

from app.core.llm.base import LLMGenerationResult, LLMGatewayError, LLMProviderBase
from app.core.llm.gateway import LLMGateway, get_llm_gateway

__all__ = [
    "LLMGateway",
    "LLMGatewayError",
    "LLMGenerationResult",
    "LLMProviderBase",
    "get_llm_gateway",
]
