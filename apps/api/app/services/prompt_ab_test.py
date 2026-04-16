"""프롬프트 A/B 테스트 프레임워크 (v0.5).

간단한 A/B 테스트 분배기:
- 템플릿 버전별 가중치 기반 랜덤 선택
- AIRequestLog에 template_name으로 기록됨
- 결과 분석은 AI 로그 집계 쿼리로 수행

사용 예
------
variant = select_variant("explain", user_id)
# variant.name = "explain_v2" or "explain_v2_detailed"
template = get_template_by_name(variant.name)
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass

from app.models.enums import AIRequestType


@dataclass
class PromptVariant:
    """A/B 테스트 변형."""
    name: str
    weight: float  # 0.0 ~ 1.0


# A/B 테스트 설정 — 현재는 단일 버전 (v2)
# 새 변형 추가 시 weights 합 = 1.0
_AB_CONFIG: dict[str, list[PromptVariant]] = {
    "explain": [
        PromptVariant(name="explain_v2", weight=1.0),
    ],
    "qa": [
        PromptVariant(name="qa_v2", weight=1.0),
    ],
}


def select_variant(
    template_group: str,
    user_id: uuid.UUID | None = None,
) -> PromptVariant:
    """A/B 분배 — user_id hash 기반 결정론적 분배.

    동일 사용자는 항상 같은 variant를 받음 (세션 일관성).
    """
    variants = _AB_CONFIG.get(template_group)
    if not variants or len(variants) == 1:
        return variants[0] if variants else PromptVariant(name=f"{template_group}_v2", weight=1.0)

    # user_id hash → 0.0~1.0 사이 값
    hash_input = str(user_id or "anonymous") + template_group
    hash_val = int(hashlib.md5(hash_input.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF

    cumulative = 0.0
    for v in variants:
        cumulative += v.weight
        if hash_val <= cumulative:
            return v
    return variants[-1]
