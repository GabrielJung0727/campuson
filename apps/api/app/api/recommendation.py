"""추천 문제 세트 라우터.

- POST /recommendation/set   — 학생 맞춤 추천 문제 세트 생성
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.question import QuestionPublic
from app.schemas.recommendation import RecommendedSetRequest, RecommendedSetResponse
from app.services.recommendation_service import (
    RecommendationError,
    build_recommended_set,
)

router = APIRouter(prefix="/recommendation", tags=["recommendation"])


@router.post(
    "/set",
    response_model=RecommendedSetResponse,
    summary="학생 맞춤 추천 문제 세트 생성",
    description=(
        "학생의 AI Profile(취약영역, level) + 오답 패턴을 기반으로 "
        "맞춤형 문제 세트를 구성합니다.\n\n"
        "전략: 반복 오답(30%) → 취약영역(40%) → 일반(30%), "
        "난이도는 level에 따라 자동 조정."
    ),
)
async def get_recommended_set(
    payload: RecommendedSetRequest,
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> RecommendedSetResponse:
    try:
        result = await build_recommended_set(
            db,
            current_user.id,
            current_user.department,
            set_size=payload.set_size,
            level=payload.level_override,
        )
    except RecommendationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return RecommendedSetResponse(
        questions=[QuestionPublic.model_validate(q) for q in result.questions],
        total_questions=len(result.questions),
        total_available=result.total_available,
        strategy=result.strategy,
        level=result.level,
        difficulty_distribution=result.difficulty_distribution,
    )
