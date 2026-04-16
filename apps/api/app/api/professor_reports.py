"""교수용 학습 분석 리포트 라우터 (v0.7).

- GET  /reports/class/{id}/students     — 학생별 성취도
- GET  /reports/class/{id}/objectives   — 학습목표별 성취도
- GET  /reports/compare                 — 분반 비교 분석
- GET  /reports/class/{id}/at-risk      — 취약 학생 탐지
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.professor_report_service import (
    compare_classes,
    detect_at_risk_students,
    get_objective_achievement,
    get_student_achievement,
)

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/class/{class_id}/students", summary="학생별 성취도 추적")
async def class_students(
    class_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await get_student_achievement(db, current_user.id, class_id)


@router.get("/class/{class_id}/objectives", summary="학습목표별 성취도")
async def class_objectives(
    class_id: uuid.UUID,
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await get_objective_achievement(db, current_user.id, class_id)


@router.get("/compare", summary="분반 비교 분석")
async def compare(
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await compare_classes(db, current_user.id)


@router.get("/class/{class_id}/at-risk", summary="취약 학생 자동 탐지")
async def at_risk(
    class_id: uuid.UUID,
    accuracy_threshold: float = Query(0.4, ge=0.1, le=0.8),
    inactivity_days: int = Query(7, ge=1, le=30),
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await detect_at_risk_students(
        db, current_user.id, class_id,
        accuracy_threshold=accuracy_threshold,
        inactivity_days=inactivity_days,
    )
