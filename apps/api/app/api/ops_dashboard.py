"""관리자 운영 대시보드 API (v0.6)."""

from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_current_user
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services import ops_dashboard_service as ops
from app.services.monitoring import get_metrics

router = APIRouter(prefix="/ops", tags=["ops-dashboard"])


def _require_admin(user: User):
    if user.role not in (Role.ADMIN, Role.DEVELOPER):
        raise HTTPException(403, "관리자 권한이 필요합니다")


@router.get("/dashboard")
async def full_dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """전체 운영 대시보드."""
    _require_admin(user)
    return await ops.get_full_dashboard(db)


@router.get("/active-users")
async def active_users(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학과별 활성 사용자 수."""
    _require_admin(user)
    return await ops.get_active_users_by_department(db)


@router.get("/weekly-learning")
async def weekly_learning(
    weeks: int = Query(4, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """주간 학습량 지표."""
    _require_admin(user)
    return await ops.get_weekly_learning_metrics(db, weeks)


@router.get("/diagnostic-completion")
async def diagnostic_completion(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """진단 테스트 완료율."""
    _require_admin(user)
    return await ops.get_diagnostic_completion_rate(db)


@router.get("/ai-usage")
async def ai_usage(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """AI 사용량/비용."""
    _require_admin(user)
    return await ops.get_ai_usage_summary(db, days)


@router.get("/accuracy-by-subject")
async def accuracy_by_subject(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """과목별 정답률."""
    _require_admin(user)
    return await ops.get_accuracy_by_subject(db)


@router.get("/assignment-completion")
async def assignment_completion(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """교수별 과제 수행률."""
    _require_admin(user)
    return await ops.get_assignment_completion_by_professor(db)


@router.get("/at-risk-students")
async def at_risk_students(
    days: int = Query(14, ge=7, le=60),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """학생 이탈 위험군."""
    _require_admin(user)
    return await ops.get_at_risk_students(db, days)


@router.get("/kb-freshness")
async def kb_freshness(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """지식베이스 문서 최신성."""
    _require_admin(user)
    return await ops.get_kb_freshness(db)


@router.get("/practicum-participation")
async def practicum_participation(
    days: int = Query(30, ge=7, le=365),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """실습 시험 참여율."""
    _require_admin(user)
    return await ops.get_practicum_participation(db, days)


@router.get("/failure-rates")
async def failure_rates(
    hours: int = Query(24, ge=1, le=168),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """장애/실패율 모니터."""
    _require_admin(user)
    return await ops.get_failure_rates(db, hours)


@router.get("/metrics")
async def realtime_metrics(
    user: User = Depends(get_current_user),
):
    """인메모리 실시간 메트릭 (API/LLM/RAG/WS)."""
    _require_admin(user)
    return get_metrics().get_summary()
