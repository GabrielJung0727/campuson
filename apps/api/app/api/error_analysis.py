"""오답 분석 고도화 라우터 (v0.7).

- GET  /analysis/difficulty-calibration — 난이도 보정 제안 (교수)
- GET  /analysis/discrimination         — 변별도 분석 (교수)
- GET  /analysis/error-blueprint        — 블루프린트 기반 오답 분석
- GET  /analysis/diagnostic-report      — 종합 진단 리포트
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.error_analysis_service import (
    analyze_errors_by_blueprint,
    calibrate_difficulty,
    compute_discrimination_index,
    generate_diagnostic_report,
)

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/difficulty-calibration", summary="문항 난이도 보정 제안 (교수)")
async def difficulty_calibration(
    min_attempts: int = Query(10, ge=5),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await calibrate_difficulty(db, current_user.department, min_attempts=min_attempts)


@router.get("/discrimination", summary="변별도 분석 (교수)")
async def discrimination(
    min_attempts: int = Query(20, ge=10),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await compute_discrimination_index(
        db, current_user.department, min_attempts=min_attempts,
    )


@router.get("/error-blueprint", summary="블루프린트 기반 오답 분석")
async def error_blueprint(
    student_id: uuid.UUID | None = Query(None, description="교수가 특정 학생 조회 시"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = current_user.id
    if student_id and current_user.role in (Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER):
        target_id = student_id
    return await analyze_errors_by_blueprint(db, target_id, current_user.department)


@router.get("/diagnostic-report", summary="종합 진단 리포트")
async def diagnostic_report(
    student_id: uuid.UUID | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    target_id = current_user.id
    if student_id and current_user.role in (Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER):
        target_id = student_id
    return await generate_diagnostic_report(db, target_id, current_user.department)
