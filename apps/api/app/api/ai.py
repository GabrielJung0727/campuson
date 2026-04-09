"""AI 라우터.

엔드포인트
---------
- POST /ai/explain   — 학생이 푼 문제(또는 일반 문제) 해설 (LLM 호출)
- POST /ai/qa        — 자유 질의응답
- GET  /ai/logs      — AIRequestLog 조회 (관리자/개발자)
- GET  /ai/me/logs   — 본인의 AI 호출 이력
- GET  /ai/info      — 현재 활성화된 LLM provider/model 정보
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import (
    get_current_active_user,
    require_roles,
)
from app.core.llm import get_llm_gateway
from app.db.session import get_db
from app.models.enums import AIRequestType, Role
from app.models.user import User
from app.schemas.ai import (
    AIGenerationMetadata,
    AIGenerationResponse,
    AIRequestLogItem,
    AIRequestLogListResponse,
    ExplainRequest,
    QARequest,
)
from app.services.ai_service import (
    AIServiceError,
    HistoryNotFoundError,
    QuestionNotFoundError,
    answer_question,
    explain_question,
    list_request_logs,
)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get(
    "/info",
    summary="현재 LLM Gateway 설정 조회",
)
async def gateway_info(
    _user: User = Depends(get_current_active_user),
) -> dict:
    """관리자/개발자가 어떤 LLM이 활성화되어 있는지 빠르게 확인하기 위한 엔드포인트."""
    gateway = get_llm_gateway()
    return {
        "provider": gateway.provider_name.value,
        "model": gateway.model,
    }


@router.post(
    "/explain",
    response_model=AIGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="문제 해설 생성 (LLM)",
    description=(
        "학생이 특정 문제에 대한 AI 해설을 요청합니다. "
        "`history_id`를 함께 보내면 학생의 풀이 결과(선택지/정오답)를 컨텍스트로 사용하고, "
        "그렇지 않으면 일반 해설을 생성합니다."
    ),
)
async def explain(
    payload: ExplainRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerationResponse:
    try:
        log, output = await explain_question(
            db,
            current_user,
            payload.question_id,
            history_id=payload.history_id,
        )
    except QuestionNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HistoryNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return AIGenerationResponse(
        request_type=AIRequestType.EXPLAIN,
        output_text=output,
        metadata=AIGenerationMetadata(
            log_id=log.id,
            provider=log.provider,
            model=log.model,
            template_name=log.template_name,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            latency_ms=log.latency_ms,
        ),
    )


@router.post(
    "/qa",
    response_model=AIGenerationResponse,
    status_code=status.HTTP_200_OK,
    summary="자유 질의응답 (LLM)",
)
async def qa(
    payload: QARequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIGenerationResponse:
    try:
        log, output = await answer_question(db, current_user, payload.question)
    except AIServiceError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)
        ) from exc

    return AIGenerationResponse(
        request_type=AIRequestType.QA,
        output_text=output,
        metadata=AIGenerationMetadata(
            log_id=log.id,
            provider=log.provider,
            model=log.model,
            template_name=log.template_name,
            input_tokens=log.input_tokens,
            output_tokens=log.output_tokens,
            latency_ms=log.latency_ms,
        ),
    )


@router.get(
    "/me/logs",
    response_model=AIRequestLogListResponse,
    summary="본인의 AI 호출 이력 조회",
)
async def list_my_logs(
    request_type: AIRequestType | None = Query(default=None),
    success_only: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AIRequestLogListResponse:
    items, total = await list_request_logs(
        db,
        user_id=current_user.id,
        request_type=request_type,
        success_only=success_only,
        page=page,
        page_size=page_size,
    )
    return AIRequestLogListResponse(
        items=[AIRequestLogItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )


@router.get(
    "/logs",
    response_model=AIRequestLogListResponse,
    summary="전체 AI 호출 이력 조회 (관리자/개발자)",
)
async def list_all_logs(
    user_id: uuid.UUID | None = Query(default=None),
    request_type: AIRequestType | None = Query(default=None),
    success_only: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    _admin: User = Depends(require_roles(Role.ADMIN, Role.DEVELOPER)),
    db: AsyncSession = Depends(get_db),
) -> AIRequestLogListResponse:
    items, total = await list_request_logs(
        db,
        user_id=user_id,
        request_type=request_type,
        success_only=success_only,
        page=page,
        page_size=page_size,
    )
    return AIRequestLogListResponse(
        items=[AIRequestLogItem.model_validate(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        has_next=(page * page_size) < total,
    )
