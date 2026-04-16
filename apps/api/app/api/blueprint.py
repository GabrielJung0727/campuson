"""국가고시 블루프린트 라우터 (v0.7).

- GET  /blueprint         — 학과별 블루프린트 조회
- POST /blueprint/seed    — 시드 데이터 적재 (ADMIN)
- GET  /blueprint/weakness — 역량 단위 약점 분석
- POST /blueprint/focus-set — 시험 직전 집중 모드 문제 세트
- GET  /blueprint/coverage — 커리큘럼 커버리지 체크 (교수)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.blueprint_service import (
    build_exam_focus_set,
    get_blueprint,
    get_competency_weakness,
    get_curriculum_coverage,
    seed_blueprint,
)

router = APIRouter(prefix="/blueprint", tags=["blueprint"])


@router.get("", summary="학과별 블루프린트 조회")
async def list_blueprint(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_blueprint(db, current_user.department)


@router.post("/seed", summary="블루프린트 시드 적재 (관리자)")
async def seed(
    current_user: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    count = await seed_blueprint(db, current_user.department)
    await db.commit()
    return {"seeded": count}


@router.get("/weakness", summary="역량 단위 약점 분석")
async def weakness(
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    return await get_competency_weakness(db, current_user.id, current_user.department)


@router.post("/focus-set", summary="시험 직전 집중 모드 문제 세트")
async def focus_set(
    set_size: int = Query(30, ge=5, le=100),
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    return await build_exam_focus_set(
        db, current_user.id, current_user.department, set_size=set_size,
    )


@router.get("/coverage", summary="커리큘럼 커버리지 체크 (교수)")
async def coverage(
    current_user: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
):
    return await get_curriculum_coverage(db, current_user.department)
