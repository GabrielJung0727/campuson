"""인증 라우터 — 회원가입/이메일인증/로그인/토큰재발급/계정찾기."""

from typing import Union

from fastapi import APIRouter, Depends, HTTPException, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.redis import get_redis
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    FindEmailRequest,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
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
    InvalidPasswordResetTokenError,
    StudentNoAlreadyExistsError,
    authenticate_user,
    confirm_password_reset,
    issue_token_pair,
    refresh_access_token,
    register_user,
    request_password_reset,
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


# === 아이디(이메일) 찾기 ===
@router.post(
    "/find-email",
    response_model=MessageResponse,
    summary="아이디 찾기 (이름 + 학번)",
    description="이름과 학번이 일치하는 사용자의 이메일(일부 마스킹)을 반환합니다.",
)
async def find_email_endpoint(
    payload: FindEmailRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    user = await db.scalar(
        select(User).where(User.name == payload.name, User.student_no == payload.student_no)
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일치하는 계정을 찾을 수 없습니다.",
        )
    # 이메일 마스킹: ab***@gmail.com
    email = user.email
    local, domain = email.split("@")
    if len(local) <= 2:
        masked = local[0] + "***"
    else:
        masked = local[:2] + "***"
    return MessageResponse(message=f"{masked}@{domain}")


# === 비밀번호 재설정 요청 ===
@router.post(
    "/request-password-reset",
    response_model=MessageResponse,
    summary="비밀번호 재설정 이메일 발송",
    description="등록된 이메일로 비밀번호 재설정 링크를 발송합니다. 보안을 위해 이메일 존재 여부를 노출하지 않습니다.",
)
async def request_password_reset_endpoint(
    payload: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    token = await request_password_reset(db, redis, payload.email)
    msg = "등록된 이메일이라면 재설정 안내가 발송되었습니다."
    if settings.env == "development" and token:
        msg += f" [DEV] token={token}"
    return MessageResponse(message=msg)


# === 비밀번호 재설정 확인 ===
@router.post(
    "/confirm-password-reset",
    response_model=MessageResponse,
    summary="비밀번호 재설정 완료",
    description="이메일로 수신한 토큰과 새 비밀번호로 비밀번호를 재설정합니다.",
    responses={400: {"description": "토큰 만료 또는 비밀번호 정책 위반"}},
)
async def confirm_password_reset_endpoint(
    payload: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> MessageResponse:
    try:
        await confirm_password_reset(db, redis, payload.token, payload.new_password)
    except (InvalidPasswordResetTokenError, AuthError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    return MessageResponse(message="비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해주세요.")
