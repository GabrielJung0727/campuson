"""Feature flag 시스템 (v0.9).

런타임 flag로 기능 on/off/롤아웃. Redis 미가용 시 ENV 기반 fallback.

사용 예
-------
```python
from app.core.feature_flags import is_enabled

if await is_enabled("practicum_realtime_ai", user=current_user):
    ...
```
"""

from __future__ import annotations

import hashlib
import logging
import os
from dataclasses import dataclass
from typing import Any

from app.core.redis import get_redis_client
from app.models.user import User

logger = logging.getLogger(__name__)

FLAG_PREFIX = "feat:"


@dataclass
class FeatureFlag:
    """Feature flag 정의."""
    key: str
    default_enabled: bool = False
    rollout_pct: int = 0  # 0~100 — 사용자 해시 기반 확률적 활성화
    allowed_roles: tuple[str, ...] = ()  # 특정 role만 타겟팅
    allowed_schools: tuple[str, ...] = ()  # 특정 학교만
    description: str = ""


# 선언된 flag 레지스트리 (신규 기능 추가 시 여기에 등록)
REGISTRY: dict[str, FeatureFlag] = {
    "practicum_realtime_ai": FeatureFlag(
        key="practicum_realtime_ai",
        default_enabled=True,
        description="실습 실시간 AI 피드백 (WS)",
    ),
    "osce_video_replay": FeatureFlag(
        key="osce_video_replay",
        default_enabled=False,
        rollout_pct=20,
        description="OSCE 비디오 리플레이 (점진 롤아웃)",
    ),
    "lms_grade_autosync": FeatureFlag(
        key="lms_grade_autosync",
        default_enabled=False,
        allowed_roles=("ADMIN", "DEVELOPER"),
        description="LMS 성적 자동 동기화",
    ),
    "kb_upload_strict_security": FeatureFlag(
        key="kb_upload_strict_security",
        default_enabled=True,
        description="KB 업로드 엄격 보안 스캔",
    ),
    "abac_enforcement": FeatureFlag(
        key="abac_enforcement",
        default_enabled=True,
        description="ABAC 정책 강제 (미활성 시 RBAC만)",
    ),
    "pii_masking": FeatureFlag(
        key="pii_masking",
        default_enabled=True,
        description="응답 PII 자동 마스킹",
    ),
}


async def _redis_override(key: str) -> str | None:
    """Redis override 조회 — '1'/'0'/'pct:N' 형식."""
    try:
        redis = get_redis_client()
        val = await redis.get(f"{FLAG_PREFIX}{key}")
        if isinstance(val, bytes):
            return val.decode()
        return val
    except Exception as exc:  # noqa: BLE001
        logger.debug("Feature flag redis lookup failed: %s", exc)
        return None


def _env_override(key: str) -> str | None:
    """환경변수 override — FEATURE_<KEY_UPPER>."""
    return os.getenv(f"FEATURE_{key.upper()}")


def _rollout_hit(user_id: str, pct: int) -> bool:
    """사용자 해시 기반 롤아웃 — 안정적 bucket."""
    if pct <= 0:
        return False
    if pct >= 100:
        return True
    h = hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()  # nosec
    bucket = int(h[:8], 16) % 100
    return bucket < pct


async def is_enabled(key: str, *, user: User | None = None) -> bool:
    """feature flag 활성 여부."""
    flag = REGISTRY.get(key)
    if flag is None:
        logger.warning("Unknown feature flag: %s", key)
        return False

    # 1. Redis override (최우선)
    override = await _redis_override(key)
    if override is not None:
        if override == "1":
            return True
        if override == "0":
            return False
        if override.startswith("pct:"):
            try:
                pct = int(override.split(":")[1])
                if user and _rollout_hit(str(user.id), pct):
                    return True
                return False
            except ValueError:
                pass

    # 2. 환경변수 override
    env = _env_override(key)
    if env is not None:
        return env.lower() in ("1", "true", "yes", "on")

    # 3. Role 타겟팅
    if flag.allowed_roles and user:
        if user.role.value not in flag.allowed_roles:
            return False

    # 4. 학교 타겟팅
    if flag.allowed_schools and user and user.school_id:
        if str(user.school_id) not in flag.allowed_schools:
            return False

    # 5. 롤아웃 % (user 있을 때만)
    if flag.rollout_pct > 0 and user:
        return _rollout_hit(str(user.id), flag.rollout_pct)

    # 6. 기본값
    return flag.default_enabled


async def set_flag(key: str, value: bool | int) -> None:
    """관리자 전용 — Redis 플래그 오버라이드."""
    redis = get_redis_client()
    if isinstance(value, bool):
        await redis.set(f"{FLAG_PREFIX}{key}", "1" if value else "0")
    elif isinstance(value, int):
        await redis.set(f"{FLAG_PREFIX}{key}", f"pct:{max(0, min(100, value))}")


async def clear_flag(key: str) -> None:
    """오버라이드 제거."""
    redis = get_redis_client()
    await redis.delete(f"{FLAG_PREFIX}{key}")


def list_flags() -> list[dict[str, Any]]:
    """등록된 flag 메타데이터 반환."""
    return [
        {
            "key": f.key,
            "default_enabled": f.default_enabled,
            "rollout_pct": f.rollout_pct,
            "allowed_roles": list(f.allowed_roles),
            "description": f.description,
        }
        for f in REGISTRY.values()
    ]
