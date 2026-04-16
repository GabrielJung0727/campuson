"""Rate limit 미들웨어 (v0.9).

Redis 기반 sliding-window 리미터:
- 인증 경로: IP/email 기반 초당 엄격 제한 (brute-force 방어)
- 일반 API: 사용자 단위 분당 제한
- 고비용 경로(LLM/업로드): 추가 quota

Redis 미가용 시 no-op으로 동작.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.redis import get_redis_client

logger = logging.getLogger(__name__)


@dataclass
class RateLimitRule:
    """단일 경로 패턴용 한도."""
    path_prefix: str
    max_requests: int
    window_seconds: int
    scope: str = "ip"  # "ip" | "user" | "user_path"


# 기본 정책 — 파이프라인 상단에서 우선 매칭
DEFAULT_RULES: list[RateLimitRule] = [
    # Auth — 로그인/패스워드 reset brute-force 방지
    RateLimitRule("/api/v1/auth/login", max_requests=10, window_seconds=60, scope="ip"),
    RateLimitRule("/api/v1/auth/register", max_requests=5, window_seconds=300, scope="ip"),
    RateLimitRule("/api/v1/auth/password-reset", max_requests=3, window_seconds=600, scope="ip"),
    # LLM — 비용 제어
    RateLimitRule("/api/v1/ai/", max_requests=30, window_seconds=60, scope="user"),
    # 업로드 — 파일 처리 파이프라인
    RateLimitRule("/api/v1/kb/upload", max_requests=20, window_seconds=300, scope="user"),
    # 일반 API 기본 한도
    RateLimitRule("/api/v1/", max_requests=300, window_seconds=60, scope="user"),
]


def _match_rule(path: str) -> RateLimitRule | None:
    for rule in DEFAULT_RULES:
        if path.startswith(rule.path_prefix):
            return rule
    return None


def _client_ip(request: Request) -> str:
    """X-Forwarded-For 우선, 없으면 client host."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _scope_key(request: Request, rule: RateLimitRule) -> str:
    ip = _client_ip(request)
    user_id = request.headers.get("x-user-id", "anon")  # 미들웨어 상단에서 세팅된 경우
    if rule.scope == "ip":
        return f"rl:{rule.path_prefix}:{ip}"
    if rule.scope == "user":
        return f"rl:{rule.path_prefix}:u:{user_id}:{ip}"
    if rule.scope == "user_path":
        return f"rl:{request.url.path}:u:{user_id}"
    return f"rl:{rule.path_prefix}:{ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 기반 레이트 리미터.

    Sliding-window: ZSET에 timestamp 기록 → 창 밖 제거 → 카운트.
    """

    async def dispatch(self, request: Request, call_next):
        # OPTIONS/health 등 가벼운 경로 제외
        if request.method == "OPTIONS" or request.url.path.endswith("/health"):
            return await call_next(request)

        rule = _match_rule(request.url.path)
        if rule is None:
            return await call_next(request)

        try:
            redis = get_redis_client()
            key = _scope_key(request, rule)
            now_ms = int(time.time() * 1000)
            window_start = now_ms - rule.window_seconds * 1000

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zadd(key, {str(now_ms): now_ms})
            pipe.zcard(key)
            pipe.expire(key, rule.window_seconds)
            _, _, count, _ = await pipe.execute()

            if count > rule.max_requests:
                retry_after = rule.window_seconds
                logger.warning(
                    "Rate limit exceeded: %s %s count=%s limit=%s",
                    request.method, request.url.path, count, rule.max_requests,
                )
                return JSONResponse(
                    status_code=429,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit": str(rule.max_requests),
                        "X-RateLimit-Window": str(rule.window_seconds),
                    },
                    content={
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": f"Too many requests. Try again in {retry_after}s.",
                            "details": {
                                "limit": rule.max_requests,
                                "window_seconds": rule.window_seconds,
                            },
                        }
                    },
                )
        except Exception as exc:  # noqa: BLE001
            # Redis 장애 시 요청 차단하지 않음 (fail-open)
            logger.debug("Rate limit check skipped: %s", exc)

        return await call_next(request)
