"""통계 라우터 — 문항별 통계 + 학생 백분위.

v0.2 엔드포인트
--------------
- GET  /stats/question/{id}   — 문항별 응답 통계 (선택지 선택률 포함)
- GET  /stats/percentile      — 본인의 학과 내 백분위
- GET  /stats/department-overview — 학과 전체 분석 (교수/관리자)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, require_roles
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.services.stats_service import get_question_stats, get_student_percentile

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get(
    "/question/{question_id}",
    summary="문항별 응답 통계 (선택지 선택률 포함)",
    description=(
        "특정 문항의 전체 학생 응답 통계를 반환합니다.\n\n"
        "- `total_attempts`: 총 응시자 수\n"
        "- `correct_count`: 정답자 수\n"
        "- `accuracy`: 정답률 (0~1)\n"
        "- `choice_distribution`: 선택지별 선택 횟수 ({\"0\": 12, \"1\": 87, ...})\n"
        "- `avg_time_sec`: 평균 풀이 시간\n"
        "- `avg_choice_changes`: 평균 선택 변경 횟수"
    ),
)
async def question_stats_endpoint(
    question_id: uuid.UUID,
    _user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await get_question_stats(db, question_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return result


@router.get(
    "/percentile",
    summary="본인의 학과 내 백분위",
    description=(
        "전체 정답률 기준으로 학과 내 몇 %인지 반환합니다.\n\n"
        "- `overall_percentile`: 전체 백분위 (예: 77이면 상위 23%)\n"
        "- `subject_percentiles`: 과목별 백분위"
    ),
)
async def percentile_endpoint(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    return await get_student_percentile(db, current_user.id, current_user.department)


@router.get(
    "/percentile/{user_id}",
    summary="특정 학생의 백분위 (교수/관리자)",
)
async def student_percentile_endpoint(
    user_id: uuid.UUID,
    _requester: User = Depends(require_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from app.models.user import User as UserModel

    target = await db.get(UserModel, user_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return await get_student_percentile(db, user_id, target.department)
