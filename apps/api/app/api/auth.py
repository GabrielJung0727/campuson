"""인증 라우터 — 회원가입/이메일인증/로그인/토큰재발급."""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import MessageResponse
from app.schemas.user import UserPublic
from app.services.auth_service import (
    AccountInactiveError,
    AuthError,
    EmailAlreadyExistsError,
    EmailVerificationError,
    InvalidCredentialsError,
    StudentNoAlreadyExistsError,
    authenticate_user,
    issue_token_pair,
    refresh_access_token,
    register_user,
    resend_verification_code,
    send_verification_code,
    verify_email,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=Union[TokenResponse, RegisterResponse],
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "검증 실패 (비밀번호 정책, 학번 형식 등)"},
        409: {"description": "이메일 또는 학번 중복"},
    },
)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse | RegisterResponse:
    """회원가입.

    - **SMTP 활성화 시**: 인증코드 이메일 발송 → RegisterResponse (토큰 없음)
    - **SMTP 비활성 + 개발 환경**: 즉시 ACTIVE → TokenResponse (바로 로그인)
    """
    try:
        user = await register_user(db, payload)
    except (EmailAlreadyExistsError, StudentNoAlreadyExistsError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    # 이메일 인증이 필요한 경우
    if not user.email_verified:
        code = await send_verification_code(db, redis, user)
        msg = "인증코드가 이메일로 발송되었습니다."
        if settings.env == "development" and code:
            msg += f" [DEV] code={code}"
        return RegisterResponse(
            message=msg,
            user_id=str(user.id),
            email=user.email,
            requires_verification=True,
        )

    # 이미 verified (개발 환경 + SMTP 비활성)
    access_token, refresh_token = issue_token_pair(user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/verify-email",
    response_model=TokenResponse,
    summary="이메일 인증코드 검증",
    description="회원가입 시 발송된 6자리 코드를 입력하여 이메일을 인증합니다. 인증 성공 시 토큰이 발급됩니다.",
    responses={400: {"description": "코드 불일치 또는 만료"}},
)
async def verify_email_endpoint(
    payload: VerifyEmailRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    try:
        user = await verify_email(db, redis, payload.email, payload.code)
    except EmailVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    access_token, refresh_token = issue_token_pair(user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/resend-verification",
    response_model=MessageResponse,
    summary="인증코드 재발송",
    description="이메일 인증코드를 재발송합니다. 사용자 존재 여부를 노출하지 않기 위해 항상 동일 응답.",
)
async def resend_verification_endpoint(
    payload: ResendVerificationRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    code = await resend_verification_code(db, redis, payload.email)
    msg = "등록된 이메일이라면 인증코드가 발송되었습니다."
    if settings.env == "development" and code:
        msg += f" [DEV] code={code}"
    return MessageResponse(message=msg)


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"description": "이메일 또는 비밀번호가 올바르지 않음"},
        403: {"description": "이메일 미인증 또는 계정 비활성"},
    },
)
async def login(
    payload: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """이메일/비밀번호 로그인."""
    try:
        user = await authenticate_user(db, payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AccountInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

    access_token, refresh_token = issue_token_pair(user)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    responses={401: {"description": "리프레시 토큰이 유효하지 않음"}},
)
async def refresh(
    payload: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
) -> AccessTokenResponse:
    """리프레시 토큰으로 액세스 토큰 재발급."""
    try:
        access_token = await refresh_access_token(db, payload.refresh_token)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return AccessTokenResponse(access_token=access_token)
