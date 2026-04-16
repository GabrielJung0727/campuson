"""LLM 비용 추적 서비스 (v0.6).

- provider별 사용량 집계
- 사용자/역할별 토큰 사용량
- 일/주/월 비용 대시보드 데이터
- 캐시 전략 (동일 질문 재사용)
- 모델 라우팅 정책
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis_client
from app.models.ai_request_log import AIRequestLog
from app.models.cost_daily import CostDaily
from app.models.enums import AIRequestType, LLMProvider, Role
from app.models.user import User

logger = logging.getLogger(__name__)

# === 비용 단가 (USD per 1M tokens) ===
# 2026-04 기준 추정 단가
COST_TABLE: dict[str, dict[str, float]] = {
    # provider/model → {"input": $/1M, "output": $/1M}
    "ANTHROPIC/claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
    "ANTHROPIC/claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "OPENAI/gpt-4o-mini": {"input": 0.15, "output": 0.6},
    "OPENAI/gpt-4o": {"input": 2.5, "output": 10.0},
    "MOCK/mock": {"input": 0.0, "output": 0.0},
}


def estimate_cost(provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 수 기반 비용 추정 (USD)."""
    key = f"{provider}/{model}"
    rates = COST_TABLE.get(key)
    if not rates:
        # 알려지지 않은 모델 → 보수적 추정
        rates = {"input": 3.0, "output": 15.0}
    return (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000


# === 일별 비용 집계 ===


async def aggregate_daily_costs(db: AsyncSession, target_date: date) -> dict:
    """특정 일자의 AIRequestLog를 집계하여 cost_daily에 저장."""
    # 기존 해당 날짜 데이터 삭제 (upsert 대신 replace)
    await db.execute(
        text("DELETE FROM cost_daily WHERE date = :d"),
        {"d": target_date},
    )

    # AIRequestLog 집계
    query = (
        select(
            AIRequestLog.provider,
            AIRequestLog.model,
            User.role,
            User.department,
            func.count().label("request_count"),
            func.sum(func.cast(AIRequestLog.success, type(1))).label("success_count"),
            func.sum(AIRequestLog.input_tokens).label("input_tokens"),
            func.sum(AIRequestLog.output_tokens).label("output_tokens"),
            func.avg(AIRequestLog.latency_ms).label("avg_latency"),
            func.percentile_cont(0.95).within_group(AIRequestLog.latency_ms).label("p95_latency"),
        )
        .outerjoin(User, AIRequestLog.user_id == User.id)
        .where(func.date(AIRequestLog.created_at) == target_date)
        .group_by(AIRequestLog.provider, AIRequestLog.model, User.role, User.department)
    )

    rows = (await db.execute(query)).all()
    inserted = 0

    for row in rows:
        provider_str = row.provider.value if row.provider else "UNKNOWN"
        role_str = row.role.value if row.role else "SYSTEM"
        dept_str = row.department.value if row.department else None
        in_tok = int(row.input_tokens or 0)
        out_tok = int(row.output_tokens or 0)
        cost = estimate_cost(provider_str, row.model, in_tok, out_tok)

        daily = CostDaily(
            date=target_date,
            provider=provider_str,
            model=row.model,
            role=role_str,
            department=dept_str,
            request_count=row.request_count,
            success_count=int(row.success_count or 0),
            error_count=row.request_count - int(row.success_count or 0),
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=in_tok + out_tok,
            estimated_cost_usd=cost,
            avg_latency_ms=int(row.avg_latency or 0),
            p95_latency_ms=int(row.p95_latency or 0),
        )
        db.add(daily)
        inserted += 1

    await db.flush()
    return {"date": str(target_date), "rows_inserted": inserted}


# === 비용 조회 ===


async def get_daily_costs(
    db: AsyncSession,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
) -> list[dict]:
    """일별 비용 조회."""
    if not end_date:
        end_date = date.today()
    if not start_date:
        start_date = end_date - timedelta(days=30)

    query = (
        select(
            CostDaily.date,
            func.sum(CostDaily.request_count).label("requests"),
            func.sum(CostDaily.input_tokens).label("input_tokens"),
            func.sum(CostDaily.output_tokens).label("output_tokens"),
            func.sum(CostDaily.total_tokens).label("total_tokens"),
            func.sum(CostDaily.estimated_cost_usd).label("cost_usd"),
        )
        .where(CostDaily.date.between(start_date, end_date))
    )
    if provider:
        query = query.where(CostDaily.provider == provider)

    query = query.group_by(CostDaily.date).order_by(CostDaily.date)
    rows = (await db.execute(query)).all()

    return [
        {
            "date": str(r.date),
            "requests": r.requests,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "total_tokens": int(r.total_tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0), 4),
        }
        for r in rows
    ]


async def get_cost_by_provider(
    db: AsyncSession, start_date: date, end_date: date,
) -> list[dict]:
    """provider별 비용 요약."""
    query = (
        select(
            CostDaily.provider,
            CostDaily.model,
            func.sum(CostDaily.request_count).label("requests"),
            func.sum(CostDaily.total_tokens).label("total_tokens"),
            func.sum(CostDaily.estimated_cost_usd).label("cost_usd"),
        )
        .where(CostDaily.date.between(start_date, end_date))
        .group_by(CostDaily.provider, CostDaily.model)
        .order_by(desc("cost_usd"))
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "provider": r.provider,
            "model": r.model,
            "requests": r.requests,
            "total_tokens": int(r.total_tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0), 4),
        }
        for r in rows
    ]


async def get_cost_by_role(
    db: AsyncSession, start_date: date, end_date: date,
) -> list[dict]:
    """역할별 토큰 사용량."""
    query = (
        select(
            CostDaily.role,
            func.sum(CostDaily.request_count).label("requests"),
            func.sum(CostDaily.input_tokens).label("input_tokens"),
            func.sum(CostDaily.output_tokens).label("output_tokens"),
            func.sum(CostDaily.estimated_cost_usd).label("cost_usd"),
        )
        .where(CostDaily.date.between(start_date, end_date))
        .group_by(CostDaily.role)
        .order_by(desc("cost_usd"))
    )
    rows = (await db.execute(query)).all()
    return [
        {
            "role": r.role,
            "requests": r.requests,
            "input_tokens": int(r.input_tokens or 0),
            "output_tokens": int(r.output_tokens or 0),
            "cost_usd": round(float(r.cost_usd or 0), 4),
        }
        for r in rows
    ]


async def get_user_token_usage(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    days: int = 30,
) -> dict:
    """개별 사용자 토큰 사용량."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.count().label("requests"),
            func.sum(AIRequestLog.input_tokens).label("input_tokens"),
            func.sum(AIRequestLog.output_tokens).label("output_tokens"),
        )
        .where(AIRequestLog.user_id == user_id, AIRequestLog.created_at >= since)
    )
    row = result.one()
    in_tok = int(row.input_tokens or 0)
    out_tok = int(row.output_tokens or 0)

    return {
        "user_id": str(user_id),
        "period_days": days,
        "requests": row.requests,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "total_tokens": in_tok + out_tok,
    }


# === 캐시 전략 — 동일 질문 재사용 ===


async def get_cached_response(query: str, department: str | None = None) -> str | None:
    """동일 질문에 대한 캐시된 응답 조회 (Redis)."""
    redis = get_redis_client()
    cache_key = _make_cache_key(query, department)
    cached = await redis.get(cache_key)
    return cached


async def set_cached_response(
    query: str, response: str, department: str | None = None, ttl: int = 3600,
) -> None:
    """응답을 캐시에 저장 (기본 TTL: 1시간)."""
    redis = get_redis_client()
    cache_key = _make_cache_key(query, department)
    await redis.setex(cache_key, ttl, response)


def _make_cache_key(query: str, department: str | None) -> str:
    """캐시 키 생성."""
    normalized = query.strip().lower()
    h = hashlib.md5(f"{department or 'ALL'}:{normalized}".encode()).hexdigest()[:16]
    return f"campuson:ai:cache:{h}"


# === 모델 라우팅 정책 ===


class ModelRouter:
    """요청 유형에 따른 고비용/저비용 모델 라우팅.

    정책:
    - 일반 풀이 설명 → 저비용 모델 (haiku/gpt-4o-mini)
    - 교수 검수 초안 → 상위 모델 (sonnet/gpt-4o)
    - RAG 없는 일반 대화 → 제한 (저비용)
    - 장문 보고서 → 별도 quota
    """

    # request_type → (provider_override, model_override, max_tokens_override)
    ROUTING_TABLE: dict[str, dict] = {
        "EXPLAIN": {
            "model": "claude-haiku-4-5-20251001" if settings.llm_provider == "anthropic" else "gpt-4o-mini",
            "max_tokens": 1024,
            "tier": "low_cost",
        },
        "QA": {
            "model": "claude-haiku-4-5-20251001" if settings.llm_provider == "anthropic" else "gpt-4o-mini",
            "max_tokens": 1024,
            "tier": "low_cost",
        },
        "PROFESSOR_REVIEW": {
            "model": settings.llm_model,  # 상위 모델 유지
            "max_tokens": 2048,
            "tier": "high_quality",
        },
        "REPORT": {
            "model": settings.llm_model,
            "max_tokens": 4096,
            "tier": "high_quality",
        },
    }

    # 역할별 일일 토큰 한도
    DAILY_LIMITS: dict[str, int] = {
        "STUDENT": 100_000,
        "PROFESSOR": 500_000,
        "ADMIN": 1_000_000,
        "DEVELOPER": 10_000_000,
    }

    # 긴 문맥 제한 (입력 토큰 임계값)
    MAX_INPUT_TOKENS = 8000

    # 응답 길이 제한 (기본값, request_type별 override 가능)
    DEFAULT_MAX_OUTPUT_TOKENS = 1024

    @classmethod
    def get_routing(cls, request_type: str, user_role: str | None = None) -> dict:
        """요청 유형 + 역할에 따른 라우팅 결과."""
        route = cls.ROUTING_TABLE.get(request_type, {
            "model": settings.llm_model,
            "max_tokens": cls.DEFAULT_MAX_OUTPUT_TOKENS,
            "tier": "default",
        })

        daily_limit = cls.DAILY_LIMITS.get(user_role or "STUDENT", 100_000)

        return {
            **route,
            "daily_token_limit": daily_limit,
            "max_input_tokens": cls.MAX_INPUT_TOKENS,
        }

    @classmethod
    async def check_quota(cls, db: AsyncSession, user_id: uuid.UUID, role: str) -> dict:
        """사용자 일일 quota 확인."""
        usage = await get_user_token_usage(db, user_id, days=1)
        limit = cls.DAILY_LIMITS.get(role, 100_000)
        used = usage["total_tokens"]

        return {
            "used": used,
            "limit": limit,
            "remaining": max(0, limit - used),
            "exceeded": used >= limit,
        }
