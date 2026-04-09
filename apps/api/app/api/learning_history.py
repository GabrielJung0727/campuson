"""학습 이력 라우터.

엔드포인트
---------
- POST /history/answer            — 풀이 제출 + 자동 채점/분류
- GET  /history/me                — 본인 풀이 이력 (페이지네이션)
- GET  /history/wrong-answers     — 본인 오답노트 (반복 오답 우선)
- GET  /history/stats             — 본인 학습 통계 (일/주/월)
- GET  /history/users/{user_id}/stats          — 권한자만 (교수 학과 스코프)
- GET  /history/users/{user_id}/wrong-answers  — 권한자만
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    require_roles,
    require_self_or_roles,
)
from app.db.session import get_db
from app.models.enums import Difficulty, ErrorType, Role
from app.models.user import User
from app.schemas.learning_history import (
    AnswerSubmitRequest,
    AnswerSubmitResponse,
    LearningHistoryListResponse,
    LearningStatsResponse,
    WrongAnswerListResponse,
)
from app.services.learning_history_service import (
    HistoryError,
    QuestionNotFoundError,
    aggregate_stats,
    list_history_for_user,
    list_wrong_answers,
    submit_answer,
)

router = APIRouter(prefix="/history", tags=["learning-history"])


@router.post(
    "/answer",
    response_model=AnswerSubmitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="문제 풀이 제출 + 자동 채점/분류",
)
async def submit_answer_endpoint(
    payload: AnswerSubmitRequest,
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> AnswerSubmitResponse:
    """학생이 문제를 풀고 응답을 제출.

    응답에는 정답/해설/오답 분류가 포함된다.
    """
    try:
        history, question = await submit_answer(
            db,
            current_user,
            payload.question_id,
            payload.selected_choice,
            payload.solving_time_sec,
        )
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HistoryError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return AnswerSubmitResponse(
        history_id=history.id,
        question_id=question.id,
        is_correct=history.is_correct,
        correct_answer=question.correct_answer,
        selected_choice=history.selected_choice,
        error_type=history.error_type,
        explanation=question.explanation,
        attempt_no=history.attempt_no,
        solving_time_sec=history.solving_time_sec,
    )


@router.get(
    "/me",
    response_model=LearningHistoryListResponse,
    summary="본인의 학습 이력 조회 (페이지네이션)",
)
async def list_my_history(
    only_wrong: bool = Query(default=False, description="True면 오답만"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LearningHistoryListResponse:
    items, total = await list_history_for_user(
        db, current_user.id, only_wrong=only_wrong, page=page, page_size=page_size
    )
    return LearningHistoryListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/wrong-answers",
    response_model=WrongAnswerListResponse,
    summary="본인 오답노트 (반복 오답 우선 정렬)",
)
async def list_my_wrong_answers(
    subject: str | None = Query(default=None),
    unit: str | None = Query(default=None),
    difficulty: Difficulty | None = Query(default=None),
    error_type: ErrorType | None = Query(default=None),
    include_resolved: bool = Query(
        default=False, description="True면 가장 최근 정답으로 마무리된 것도 포함"
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> WrongAnswerListResponse:
    items, total = await list_wrong_answers(
        db,
        current_user.id,
        subject=subject,
        unit=unit,
        difficulty=difficulty,
        error_type=error_type,
        include_resolved=include_resolved,
        page=page,
        page_size=page_size,
    )
    return WrongAnswerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/stats",
    response_model=LearningStatsResponse,
    summary="본인 학습 통계 (일/주/월 시계열 + 과목별 + 오답분포)",
)
async def get_my_stats(
    period: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
    days: int | None = Query(default=None, ge=1, le=730),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> LearningStatsResponse:
    return await aggregate_stats(db, current_user.id, period=period, days=days)


# === 권한자용 ===


@router.get(
    "/users/{user_id}/stats",
    response_model=LearningStatsResponse,
    summary="특정 사용자의 학습 통계 (교수 학과 스코프 + 관리자)",
)
async def get_user_stats(
    user_id: uuid.UUID,
    period: Literal["daily", "weekly", "monthly"] = Query(default="daily"),
    days: int | None = Query(default=None, ge=1, le=730),
    _requester: User = Depends(
        require_self_or_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> LearningStatsResponse:
    return await aggregate_stats(db, user_id, period=period, days=days)


@router.get(
    "/users/{user_id}/wrong-answers",
    response_model=WrongAnswerListResponse,
    summary="특정 사용자의 오답노트 (권한자)",
)
async def get_user_wrong_answers(
    user_id: uuid.UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    include_resolved: bool = Query(default=False),
    _requester: User = Depends(
        require_self_or_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> WrongAnswerListResponse:
    items, total = await list_wrong_answers(
        db,
        user_id,
        include_resolved=include_resolved,
        page=page,
        page_size=page_size,
    )
    return WrongAnswerListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )
