"""인증 라우터 — 회원가입/이메일인증/로그인/토큰재발급/로그아웃/계정찾기."""

import uuid
from datetime import UTC, datetime
from typing import Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_active_user
from app.core.redis import get_redis
from app.core.security import TokenError, decode_token
from app.core.token_blacklist import (
    add_to_blacklist,
    revoke_refresh_family,
    revoke_user_all_tokens,
)
from app.db.session import get_db
from app.models.token_blacklist import RefreshToken, RevocationReason
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


def _get_client_meta(request: Request) -> tuple[str | None, str | None]:
    """요청에서 User-Agent + IP 추출."""
    ua = request.headers.get("user-agent")
    # X-Forwarded-For 우선 (프록시 뒤에서 실행 시)
    forwarded = request.headers.get("x-forwarded-for")
    ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else None)
    return ua, ip

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
    request: Request,
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
    ua, ip = _get_client_meta(request)
    access_token, refresh_token = await issue_token_pair(db, user, user_agent=ua, ip_address=ip)
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> TokenResponse:
    try:
        user = await verify_email(db, redis, payload.email, payload.code)
    except EmailVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    ua, ip = _get_client_meta(request)
    access_token, refresh_token = await issue_token_pair(db, user, user_agent=ua, ip_address=ip)
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
    request: Request,
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

    ua, ip = _get_client_meta(request)
    access_token, refresh_token = await issue_token_pair(db, user, user_agent=ua, ip_address=ip)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserPublic.model_validate(user),
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"description": "리프레시 토큰이 유효하지 않음 또는 재사용 탐지"}},
    summary="토큰 회전(rotation): 새 access+refresh 쌍 발급",
    description=(
        "리프레시 토큰으로 새 토큰 쌍 발급. **이전 리프레시 토큰은 즉시 폐기되며, 재사용 시 family 전체가 revoke됩니다.**"
    ),
)
async def refresh(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """리프레시 토큰 회전 (rotation) + 재사용 탐지."""
    try:
        ua, ip = _get_client_meta(request)
        access_token, new_refresh_token = await refresh_access_token(
            db, payload.refresh_token, user_agent=ua, ip_address=ip,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    # 새 access 토큰에서 user_id 추출해서 UserPublic 직렬화
    from app.core.security import decode_token as _decode
    payload_data = _decode(access_token, expected_type="access")
    user = await db.get(User, uuid.UUID(payload_data["sub"]))
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserPublic.model_validate(user),
    )


# === 로그아웃 (v1.0 보안) ===
@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="로그아웃 — 현재 세션만 종료",
    description=(
        "현재 access token의 jti를 블랙리스트에 추가하고, 제공된 refresh token family 전체를 revoke합니다."
    ),
)
async def logout(
    request: Request,
    payload: RefreshTokenRequest | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """현재 세션 로그아웃.

    동작
    ----
    1. 현재 access token의 jti를 블랙리스트에 추가 (남은 exp 동안 유효)
    2. refresh_token이 body에 있으면 해당 family 전체를 revoke
    """
    access_jti = getattr(request.state, "token_jti", None)
    access_exp = getattr(request.state, "token_exp", None)

    if access_jti and access_exp:
        await add_to_blacklist(
            db,
            jti=access_jti,
            user_id=current_user.id,
            expires_at=datetime.fromtimestamp(access_exp, tz=UTC),
            reason=RevocationReason.LOGOUT,
        )

    # refresh token family revoke (있는 경우)
    if payload and payload.refresh_token:
        try:
            rt_payload = decode_token(payload.refresh_token, expected_type="refresh")
            rt_jti = rt_payload.get("jti")
            if rt_jti:
                rt_record = await db.scalar(
                    select(RefreshToken).where(RefreshToken.jti == rt_jti)
                )
                if rt_record:
                    await revoke_refresh_family(
                        db, rt_record.family_id, RevocationReason.LOGOUT,
                    )
        except TokenError:
            pass  # 이미 무효한 refresh token은 무시

    return MessageResponse(message="로그아웃되었습니다.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="모든 기기에서 로그아웃",
    description=(
        "사용자의 모든 세션(모든 기기)을 종료합니다. 현재 토큰뿐만 아니라 이전에 발급된 모든 토큰이 무효화됩니다."
    ),
)
async def logout_all(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """모든 세션 종료.

    동작
    ----
    1. Redis에 user_revoke:{user_id} 마커 설정 (현재 시각)
       → 이 시점 이전 iat를 가진 토큰은 모두 거부됨
    2. DB의 모든 유효한 refresh token을 revoke
    3. 현재 access token도 블랙리스트 추가
    """
    revoked_count = await revoke_user_all_tokens(
        db, current_user.id, RevocationReason.LOGOUT_ALL,
    )

    # 현재 access token도 명시적으로 블랙리스트 추가
    access_jti = getattr(request.state, "token_jti", None)
    access_exp = getattr(request.state, "token_exp", None)
    if access_jti and access_exp:
        await add_to_blacklist(
            db,
            jti=access_jti,
            user_id=current_user.id,
            expires_at=datetime.fromtimestamp(access_exp, tz=UTC),
            reason=RevocationReason.LOGOUT_ALL,
        )

    return MessageResponse(
        message=f"모든 기기에서 로그아웃되었습니다. ({revoked_count}개 세션 종료)"
    )


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
