"""인증 서비스 — 회원가입/로그인/토큰 재발급/비밀번호 변경/재설정."""

import logging
import uuid
from datetime import UTC, datetime

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    PasswordPolicyError,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_secure_token,
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.models.enums import Role, UserStatus
from app.models.user import User
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.student_no_validator import (
    StudentNoValidationError,
    validate_student_no_for_role,
)

logger = logging.getLogger(__name__)

PASSWORD_RESET_KEY_PREFIX = "pwreset:"


class AuthError(Exception):
    """인증 관련 비즈니스 예외."""

    pass


class EmailAlreadyExistsError(AuthError):
    pass


class StudentNoAlreadyExistsError(AuthError):
    pass


class InvalidCredentialsError(AuthError):
    pass


class AccountInactiveError(AuthError):
    pass


class InvalidPasswordResetTokenError(AuthError):
    pass


# --- 회원가입 ---
async def register_user(db: AsyncSession, payload: RegisterRequest) -> User:
    """신규 사용자 등록.

    검증 단계
    --------
    1. 비밀번호 정책
    2. 학번 검증 (역할에 따라)
    3. 이메일/학번 중복 체크
    4. 비밀번호 해싱 후 저장

    Notes
    -----
    학생 가입은 PENDING 상태로 시작하며, 관리자가 학과 인증을 승인하면 ACTIVE로 전환된다.
    개발 환경에서는 가입 즉시 ACTIVE로 만들고 싶다면 settings.env로 분기할 수 있다.
    """
    try:
        validate_password_policy(payload.password)
    except PasswordPolicyError as exc:
        raise AuthError(str(exc)) from exc

    try:
        validate_student_no_for_role(payload.student_no, payload.role, payload.department)
    except StudentNoValidationError as exc:
        raise AuthError(str(exc)) from exc

    # 이메일 중복 체크
    existing_email = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing_email is not None:
        raise EmailAlreadyExistsError("이미 가입된 이메일입니다.")

    # 학번 중복 체크 (학생만)
    if payload.student_no:
        existing_student = await db.scalar(
            select(User).where(User.student_no == payload.student_no)
        )
        if existing_student is not None:
            raise StudentNoAlreadyExistsError("이미 가입된 학번입니다.")

    # PENDING으로 시작 (개발 환경은 즉시 ACTIVE)
    initial_status = UserStatus.ACTIVE if settings.env == "development" else UserStatus.PENDING

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        name=payload.name,
        student_no=payload.student_no,
        department=payload.department,
        role=payload.role,
        status=initial_status,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        # race condition 방어 — 이메일/학번 동시 가입
        raise AuthError("가입 실패: 이미 사용 중인 이메일 또는 학번입니다.") from exc

    await db.refresh(user)
    return user


# --- 로그인 ---
async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> User:
    """이메일/비밀번호로 사용자 인증.

    실패 사유를 외부에 자세히 노출하지 않기 위해 모든 실패는 InvalidCredentialsError로 통합.
    """
    user = await db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None:
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    if not verify_password(payload.password, user.password_hash):
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    if user.status == UserStatus.DELETED:
        raise InvalidCredentialsError("이메일 또는 비밀번호가 올바르지 않습니다.")

    if user.status != UserStatus.ACTIVE:
        raise AccountInactiveError(
            f"계정이 {user.status.value} 상태입니다. 관리자에게 문의하세요."
        )

    user.last_login_at = datetime.now(UTC)
    await db.flush()
    return user


def issue_token_pair(user: User) -> tuple[str, str]:
    """주어진 사용자에 대한 (access, refresh) 토큰 쌍 발급."""
    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.value, "dept": user.department.value},
    )
    refresh_token = create_refresh_token(subject=str(user.id))
    return access_token, refresh_token


# --- 토큰 재발급 ---
async def refresh_access_token(db: AsyncSession, refresh_token: str) -> str:
    """리프레시 토큰으로 새로운 액세스 토큰 발급."""
    try:
        payload = decode_token(refresh_token, expected_type="refresh")
    except TokenError as exc:
        raise InvalidCredentialsError("Invalid refresh token") from exc

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise InvalidCredentialsError("Invalid refresh token payload")
    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        raise InvalidCredentialsError("Invalid refresh token payload") from exc

    user = await db.get(User, user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise InvalidCredentialsError("User not found or inactive")

    return create_access_token(
        subject=str(user.id),
        extra_claims={"role": user.role.value, "dept": user.department.value},
    )


# --- 비밀번호 변경 (로그인 상태) ---
async def change_password(
    db: AsyncSession,
    user: User,
    current_password: str,
    new_password: str,
) -> None:
    """본인 비밀번호 변경."""
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("현재 비밀번호가 올바르지 않습니다.")

    try:
        validate_password_policy(new_password)
    except PasswordPolicyError as exc:
        raise AuthError(str(exc)) from exc

    user.password_hash = hash_password(new_password)
    await db.flush()


# --- 비밀번호 재설정 (이메일 토큰) ---
async def request_password_reset(
    db: AsyncSession,
    redis: Redis,
    email: str,
) -> str | None:
    """비밀번호 재설정 토큰 발급.

    Returns
    -------
    str | None
        개발 환경에서는 토큰을 직접 반환 (메일 전송 mock).
        프로덕션에서는 이메일로 발송하고 None을 반환해야 한다.

    Notes
    -----
    사용자 존재 여부를 노출하지 않기 위해 이메일이 없어도 예외를 발생시키지 않고
    None을 반환한다 (호출자도 항상 동일 응답을 보내야 한다).
    """
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if user is None or user.status == UserStatus.DELETED:
        logger.info("Password reset requested for non-existent email: %s", email)
        return None

    token = generate_secure_token(32)
    key = f"{PASSWORD_RESET_KEY_PREFIX}{token}"
    ttl_seconds = settings.password_reset_token_expire_minutes * 60
    await redis.setex(key, ttl_seconds, str(user.id))

    # TODO: 실제 이메일 발송 모듈 연동 (Day 14 또는 그 이전)
    logger.warning(
        "[MOCK EMAIL] Password reset token for %s: %s (expires in %d minutes)",
        user.email,
        token,
        settings.password_reset_token_expire_minutes,
    )

    if settings.env == "development":
        return token
    return None


async def confirm_password_reset(
    db: AsyncSession,
    redis: Redis,
    token: str,
    new_password: str,
) -> None:
    """비밀번호 재설정 토큰 검증 + 새 비밀번호 적용."""
    key = f"{PASSWORD_RESET_KEY_PREFIX}{token}"
    user_id_str = await redis.get(key)
    if user_id_str is None:
        raise InvalidPasswordResetTokenError("토큰이 유효하지 않거나 만료되었습니다.")

    try:
        validate_password_policy(new_password)
    except PasswordPolicyError as exc:
        raise AuthError(str(exc)) from exc

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as exc:
        await redis.delete(key)
        raise InvalidPasswordResetTokenError("토큰 데이터가 손상되었습니다.") from exc

    user = await db.get(User, user_id)
    if user is None:
        await redis.delete(key)
        raise InvalidPasswordResetTokenError("사용자를 찾을 수 없습니다.")

    user.password_hash = hash_password(new_password)
    await db.flush()
    await redis.delete(key)
    logger.info("Password reset confirmed for user %s", user.email)
