"""비밀번호 재설정 라우터 — 이메일 토큰 기반."""

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.auth import PasswordResetConfirm, PasswordResetRequest
from app.schemas.common import MessageResponse
from app.services.auth_service import (
    AuthError,
    InvalidPasswordResetTokenError,
    confirm_password_reset,
    request_password_reset,
)

router = APIRouter(prefix="/auth/password-reset", tags=["auth"])


@router.post(
    "/request",
    response_model=MessageResponse,
    summary="비밀번호 재설정 토큰 발급 요청",
    description=(
        "이메일로 재설정 링크를 전송합니다. "
        "사용자 존재 여부를 노출하지 않기 위해 항상 동일한 응답을 반환합니다. "
        "개발 환경에서는 응답 message에 토큰이 포함됩니다."
    ),
)
async def request_reset(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    """재설정 토큰 요청."""
    token = await request_password_reset(db, redis, payload.email)

    if settings.env == "development" and token:
        return MessageResponse(
            message=f"[DEV] 재설정 토큰이 발급되었습니다. token={token}"
        )
    return MessageResponse(
        message="입력하신 이메일이 등록되어 있다면 재설정 링크를 발송했습니다."
    )


@router.post(
    "/confirm",
    response_model=MessageResponse,
    responses={
        400: {"description": "토큰 무효 또는 비밀번호 정책 위반"},
    },
)
async def confirm_reset(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    """토큰 검증 + 새 비밀번호 적용."""
    try:
        await confirm_password_reset(db, redis, payload.token, payload.new_password)
    except InvalidPasswordResetTokenError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return MessageResponse(message="비밀번호가 재설정되었습니다.")
