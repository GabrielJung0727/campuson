"""임베딩 Gateway 패키지.

LLM Gateway와 유사한 패턴으로 Provider 추상화 + Mock fallback.

사용 예
-------
```python
from app.core.embeddings import get_embedding_gateway

gw = get_embedding_gateway()
vectors = await gw.embed_batch(["심방세동 정의", "모세기관지염 간호"])
assert len(vectors) == 2
assert len(vectors[0]) == gw.dimensions
```
"""

from app.core.embeddings.base import (
    EmbeddingError,
    EmbeddingProviderBase,
    EmbeddingResult,
)
from app.core.embeddings.gateway import EmbeddingGateway, get_embedding_gateway

__all__ = [
    "EmbeddingError",
    "EmbeddingGateway",
    "EmbeddingProviderBase",
    "EmbeddingResult",
    "get_embedding_gateway",
]
