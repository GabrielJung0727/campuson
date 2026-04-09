"""진단 테스트 라우터.

엔드포인트
---------
- POST /diagnostic/start             — 학생 본인이 진단 테스트 시작 (1회 제한)
- POST /diagnostic/{test_id}/submit  — 응답 제출 + 채점 + AI 프로파일 자동 생성
- GET  /diagnostic/me                — 본인 진단 결과 + AI 프로파일
- GET  /diagnostic/users/{user_id}   — 특정 학생 결과 (교수 학과 스코프 + 관리자)
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    require_roles,
    require_self_or_roles,
)
from app.db.session import get_db
from app.models.enums import Role
from app.models.user import User
from app.schemas.diagnostic import (
    AIProfileResponse,
    DiagnosticResultResponse,
    DiagnosticStartResponse,
    DiagnosticSubmitRequest,
)
from app.schemas.question import QuestionPublic
from app.services.ai_profile_service import (
    create_or_replace_profile_from_diagnostic,
    get_profile_for_user,
)
from app.services.diagnostic_service import (
    AlreadyTakenError,
    DiagnosticError,
    InsufficientQuestionsError,
    TestAlreadyCompletedError,
    TestNotFoundError,
    get_diagnostic_test_for_user,
    start_diagnostic_test,
    submit_diagnostic_test,
)

router = APIRouter(prefix="/diagnostic", tags=["diagnostic"])


@router.post(
    "/start",
    response_model=DiagnosticStartResponse,
    status_code=status.HTTP_201_CREATED,
    summary="진단 테스트 시작 (1회 제한)",
)
async def start_test(
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> DiagnosticStartResponse:
    """학생 본인의 진단 테스트를 시작.

    - 사용자당 1회만 응시 가능 (재시작 불가)
    - 학과 내 과목 균등 + 난이도 비율(EASY 30 / MEDIUM 50 / HARD 20)로 30문항 자동 구성
    - 학생은 응답에 포함된 `questions`(정답 제외)를 풀이 후 `/submit`으로 제출
    """
    try:
        test = await start_diagnostic_test(db, current_user)
    except AlreadyTakenError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except InsufficientQuestionsError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    questions: list = getattr(test, "_questions_for_response", [])
    return DiagnosticStartResponse(
        test_id=test.id,
        started_at=test.started_at,
        total_questions=len(questions),
        questions=[QuestionPublic.model_validate(q) for q in questions],
    )


@router.post(
    "/{test_id}/submit",
    response_model=DiagnosticResultResponse,
    summary="진단 테스트 응답 제출 + 채점",
)
async def submit_test(
    test_id: uuid.UUID,
    payload: DiagnosticSubmitRequest,
    current_user: User = Depends(require_roles(Role.STUDENT)),
    db: AsyncSession = Depends(get_db),
) -> DiagnosticResultResponse:
    """응답을 채점하고 AI 프로파일을 자동 생성한다.

    채점 결과
    --------
    - `total_score` (전체 정답률)
    - `section_scores` (과목별 정답률)
    - `weak_areas` (취약영역 우선순위 배열)
    - `level` (BEGINNER / INTERMEDIATE / ADVANCED 자동 결정)

    제출 직후 같은 트랜잭션에서 AIProfile이 생성/갱신된다.
    """
    try:
        test = await submit_diagnostic_test(db, current_user, test_id, payload.answers)
    except TestNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except TestAlreadyCompletedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except DiagnosticError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # AI 프로파일 자동 생성/갱신
    await create_or_replace_profile_from_diagnostic(db, test)

    return DiagnosticResultResponse(
        id=test.id,
        user_id=test.user_id,
        started_at=test.started_at,
        completed_at=test.completed_at,
        total_score=test.total_score,
        section_scores=test.section_scores,
        weak_areas=test.weak_areas,
        level=test.level,
        answer_count=len(test.answers),
    )


@router.get(
    "/me",
    response_model=DiagnosticResultResponse,
    summary="본인의 진단 테스트 결과 조회",
    responses={404: {"description": "아직 응시하지 않음"}},
)
async def get_my_result(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> DiagnosticResultResponse:
    test = await get_diagnostic_test_for_user(db, current_user.id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="아직 진단 테스트를 응시하지 않았습니다.",
        )
    return DiagnosticResultResponse(
        id=test.id,
        user_id=test.user_id,
        started_at=test.started_at,
        completed_at=test.completed_at,
        total_score=test.total_score,
        section_scores=test.section_scores,
        weak_areas=test.weak_areas,
        level=test.level,
        answer_count=len(test.answers),
    )


@router.get(
    "/users/{user_id}",
    response_model=DiagnosticResultResponse,
    summary="특정 사용자의 진단 결과 조회 (교수 학과 스코프 + 관리자)",
)
async def get_user_result(
    user_id: uuid.UUID,
    _requester: User = Depends(
        require_self_or_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> DiagnosticResultResponse:
    test = await get_diagnostic_test_for_user(db, user_id)
    if test is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="대상 사용자가 아직 진단 테스트를 응시하지 않았습니다.",
        )
    return DiagnosticResultResponse(
        id=test.id,
        user_id=test.user_id,
        started_at=test.started_at,
        completed_at=test.completed_at,
        total_score=test.total_score,
        section_scores=test.section_scores,
        weak_areas=test.weak_areas,
        level=test.level,
        answer_count=len(test.answers),
    )


# === AI Profile ===


@router.get(
    "/me/profile",
    response_model=AIProfileResponse,
    summary="본인 AI 프로파일 조회",
)
async def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIProfileResponse:
    profile = await get_profile_for_user(db, current_user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI 프로파일이 없습니다. 먼저 진단 테스트를 응시하세요.",
        )
    return AIProfileResponse.model_validate(
        {
            **profile.__dict__,
            "explanation_pref": profile.explanation_pref.value,
        }
    )


@router.get(
    "/users/{user_id}/profile",
    response_model=AIProfileResponse,
    summary="특정 사용자의 AI 프로파일 조회 (권한자)",
)
async def get_user_profile(
    user_id: uuid.UUID,
    _requester: User = Depends(
        require_self_or_roles(Role.PROFESSOR, Role.ADMIN, Role.DEVELOPER)
    ),
    db: AsyncSession = Depends(get_db),
) -> AIProfileResponse:
    profile = await get_profile_for_user(db, user_id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI 프로파일이 없습니다.",
        )
    return AIProfileResponse.model_validate(
        {
            **profile.__dict__,
            "explanation_pref": profile.explanation_pref.value,
        }
    )
