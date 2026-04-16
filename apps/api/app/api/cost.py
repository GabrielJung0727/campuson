"""비용 추적 API (v0.6)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.cost_service import (
    ModelRouter,
    aggregate_daily_costs,
    get_cost_by_provider,
    get_cost_by_role,
    get_daily_costs,
    get_user_token_usage,
)

router = APIRouter(prefix="/cost", tags=["cost"])


@router.get("/daily")
async def daily_costs(
    start_date: date | None = None,
    end_date: date | None = None,
    provider: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """일별 비용 조회."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    return await get_daily_costs(db, start_date=start_date, end_date=end_date, provider=provider)


@router.get("/by-provider")
async def costs_by_provider(
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """provider별 비용 요약."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=30))
    return await get_cost_by_provider(db, start, end)


@router.get("/by-role")
async def costs_by_role(
    start_date: date | None = None,
    end_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """역할별 토큰 사용량."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    end = end_date or date.today()
    start = start_date or (end - timedelta(days=30))
    return await get_cost_by_role(db, start, end)


@router.get("/my-usage")
async def my_usage(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 토큰 사용량."""
    return await get_user_token_usage(db, user.id, days=days)


@router.get("/my-quota")
async def my_quota(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내 일일 quota 확인."""
    return await ModelRouter.check_quota(db, user.id, user.role.value)


@router.get("/routing")
async def model_routing(
    request_type: str = "EXPLAIN",
    user: User = Depends(get_current_user),
):
    """모델 라우팅 정책 조회."""
    return ModelRouter.get_routing(request_type, user.role.value)


@router.post("/aggregate")
async def trigger_aggregation(
    target_date: date | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """비용 집계 수동 실행. ADMIN 이상만."""
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "관리자 권한이 필요합니다")
    result = await aggregate_daily_costs(db, target_date or date.today())
    return result
