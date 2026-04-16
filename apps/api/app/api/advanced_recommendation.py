"""적응형 추천 엔진 v2 라우터 (v0.7).

- POST /recommendation/adaptive   — 적응형 추천 문제 세트 (7-signal)
"""

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.advanced_recommendation import build_adaptive_set

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.post("/adaptive", summary="적응형 추천 문제 세트 (v2)")
async def adaptive_set(
    set_size: int = Body(20, ge=5, le=50),
    exam_date: str | None = Body(None, description="시험 일자 (ISO format)"),
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
):
    exam_dt = datetime.fromisoformat(exam_date) if exam_date else None
    return await build_adaptive_set(
        db,
        current_user.id,
        current_user.department,
        set_size=set_size,
        exam_date=exam_dt,
    )
