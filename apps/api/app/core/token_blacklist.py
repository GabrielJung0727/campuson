"""JWT 토큰 블랙리스트 서비스 (Redis primary + Postgres fallback).

Redis 다운 시에도 DB에서 체크할 수 있도록 이중 저장.
Redis TTL = 토큰 exp와 동일하게 설정하여 자동 정리.

키 설계
------
- `blacklist:{jti}` → "1" (TTL = 토큰 남은 수명)
- `user_revoke:{user_id}` → timestamp (logout-all 이후 발급된 토큰만 유효)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.token_blacklist import RefreshToken, RevocationReason, TokenBlacklist

logger = logging.getLogger(__name__)

BLACKLIST_KEY_PREFIX = "blacklist:"
USER_REVOKE_PREFIX = "user_revoke:"


async def add_to_blacklist(
    db: AsyncSession,
    *,
    jti: str,
    user_id: uuid.UUID,
    expires_at: datetime,
    reason: RevocationReason,
    note: str | None = None,
) -> None:
    """토큰을 블랙리스트에 추가 (Redis + DB 이중 저장)."""
    # 1. DB 저장 (영구, fallback)
    entry = TokenBlacklist(
        jti=jti,
        user_id=user_id,
        expires_at=expires_at,
        reason=reason,
        note=note,
    )
    db.add(entry)
    try:
        await db.flush()
    except Exception as exc:  # 중복 jti 등
        logger.warning("Failed to insert token blacklist: %s", exc)
        await db.rollback()

    # 2. Redis 저장 (빠른 조회, TTL 기반 자동 정리)
    try:
        redis = get_redis_client()
        ttl = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        await redis.setex(f"{BLACKLIST_KEY_PREFIX}{jti}", ttl, "1")
    except Exception as exc:
        logger.warning("Redis blacklist write failed (DB fallback in effect): %s", exc)


async def is_blacklisted(db: AsyncSession, jti: str) -> bool:
    """토큰이 블랙리스트에 있는지 확인.

    Redis를 먼저 조회 → 다운 시 DB fallback.
    """
    # 1. Redis 조회
    try:
        redis = get_redis_client()
        hit = await redis.get(f"{BLACKLIST_KEY_PREFIX}{jti}")
        if hit is not None:
            return True
    except Exception as exc:
        logger.debug("Redis blacklist check failed, falling back to DB: %s", exc)

    # 2. DB fallback
    stmt = (
        select(TokenBlacklist)
        .where(
            TokenBlacklist.jti == jti,
            TokenBlacklist.expires_at > datetime.now(UTC),
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def revoke_user_all_tokens(
    db: AsyncSession,
    user_id: uuid.UUID,
    reason: RevocationReason = RevocationReason.LOGOUT_ALL,
) -> int:
    """사용자의 모든 유효한 refresh token을 revoke + "이후 발급된 토큰만 유효" 마커 저장.

    Returns: 폐기된 refresh token 수
    """
    now = datetime.now(UTC)

    # Redis: "이 시점 이후 iat인 토큰만 유효" 마커 설정 (최대 refresh TTL만큼 유지)
    try:
        from app.core.config import settings
        redis = get_redis_client()
        ttl = settings.jwt_refresh_token_expire_days * 86400
        await redis.setex(
            f"{USER_REVOKE_PREFIX}{user_id}",
            ttl,
            str(int(now.timestamp())),
        )
    except Exception as exc:
        logger.warning("Redis user_revoke marker failed: %s", exc)

    # DB: 사용자의 유효한 refresh token 전부 revoke
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now, revoke_reason=reason)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.rowcount or 0


async def is_user_globally_revoked(user_id: uuid.UUID, token_iat: int) -> bool:
    """토큰 발급 시점(iat)이 user_revoke 마커보다 이전인지 확인.

    True = 토큰이 전역 로그아웃 이전에 발급됨 → 거부해야 함.
    """
    try:
        redis = get_redis_client()
        marker = await redis.get(f"{USER_REVOKE_PREFIX}{user_id}")
        if marker is None:
            return False
        return int(marker) > token_iat
    except Exception:
        return False


async def revoke_refresh_family(
    db: AsyncSession,
    family_id: uuid.UUID,
    reason: RevocationReason = RevocationReason.REUSE_DETECTED,
) -> int:
    """특정 family의 모든 refresh token을 revoke (재사용 탐지 시)."""
    now = datetime.now(UTC)
    stmt = (
        update(RefreshToken)
        .where(
            RefreshToken.family_id == family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now, revoke_reason=reason)
    )
    result = await db.execute(stmt)
    await db.flush()
    logger.warning(
        "Refresh family revoked: family_id=%s, reason=%s, count=%s",
        family_id, reason.value, result.rowcount,
    )
    return result.rowcount or 0


async def cleanup_expired_tokens(db: AsyncSession) -> dict[str, int]:
    """만료된 블랙리스트/리프레시 토큰 DB 정리.

    주기적 GC 잡 (CLEANUP_EXPIRED_TOKENS)에서 호출.
    """
    now = datetime.now(UTC)
    bl_stmt = delete(TokenBlacklist).where(TokenBlacklist.expires_at < now)
    bl_result = await db.execute(bl_stmt)

    rt_stmt = delete(RefreshToken).where(RefreshToken.expires_at < now)
    rt_result = await db.execute(rt_stmt)

    await db.flush()
    return {
        "blacklist_deleted": bl_result.rowcount or 0,
        "refresh_deleted": rt_result.rowcount or 0,
    }
