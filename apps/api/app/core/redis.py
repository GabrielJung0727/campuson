"""Redis 비동기 클라이언트 — 비밀번호 재설정 토큰, 캐시 등에 사용."""

from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from app.core.config import settings

_redis_client: Redis | None = None


def get_redis_client() -> Redis:
    """싱글톤 Redis 클라이언트.

    `get_redis()`를 의존성으로 쓰는 것을 권장하지만, 미들웨어 등 의존성 주입이 어려운
    위치에서는 이 함수를 직접 사용할 수 있다.
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _redis_client


async def get_redis() -> AsyncGenerator[Redis, None]:
    """FastAPI 의존성 주입용 Redis 제공자."""
    client = get_redis_client()
    try:
        yield client
    finally:
        # 싱글톤이므로 명시적 close 안 함 (앱 종료 시 일괄 해제)
        pass


async def close_redis() -> None:
    """앱 종료 시 호출 — 싱글톤 클라이언트 정리."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
