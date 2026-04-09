"""보안 유틸리티 — 비밀번호 해싱, JWT 인코딩/디코딩, 비밀번호 정책."""

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# --- 비밀번호 해싱 ---
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=settings.bcrypt_rounds,
)


def hash_password(plain_password: str) -> str:
    """평문 비밀번호를 bcrypt로 해싱합니다."""
    return pwd_context.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """비밀번호 검증."""
    return pwd_context.verify(plain_password, hashed_password)


# --- 비밀번호 정책 ---
class PasswordPolicyError(ValueError):
    """비밀번호 정책 위반."""

    pass


def validate_password_policy(password: str) -> None:
    """비밀번호 정책 검증.

    규칙
    ----
    - 최소 길이 (settings.password_min_length, 기본 8)
    - 최소 1개의 영문자 포함
    - 최소 1개의 숫자 포함
    - 공백 불가

    Raises
    ------
    PasswordPolicyError
        정책 위반 시.
    """
    if len(password) < settings.password_min_length:
        raise PasswordPolicyError(
            f"비밀번호는 최소 {settings.password_min_length}자 이상이어야 합니다."
        )
    if " " in password:
        raise PasswordPolicyError("비밀번호에 공백을 포함할 수 없습니다.")
    if not re.search(r"[A-Za-z]", password):
        raise PasswordPolicyError("비밀번호는 최소 1개의 영문자를 포함해야 합니다.")
    if not re.search(r"\d", password):
        raise PasswordPolicyError("비밀번호는 최소 1개의 숫자를 포함해야 합니다.")


# --- JWT ---
TokenType = Literal["access", "refresh"]


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """JWT 토큰 생성 (내부)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": secrets.token_urlsafe(16),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str, extra_claims: dict[str, Any] | None = None) -> str:
    """액세스 토큰 발급."""
    return _create_token(
        subject=subject,
        token_type="access",
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
        extra_claims=extra_claims,
    )


def create_refresh_token(subject: str) -> str:
    """리프레시 토큰 발급."""
    return _create_token(
        subject=subject,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )


class TokenError(Exception):
    """JWT 디코딩 실패."""

    pass


def decode_token(token: str, expected_type: TokenType | None = None) -> dict[str, Any]:
    """JWT 디코딩 + 타입 검증.

    Raises
    ------
    TokenError
        토큰이 유효하지 않거나 타입이 일치하지 않을 때.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc

    if expected_type and payload.get("type") != expected_type:
        raise TokenError(f"Expected token type {expected_type}, got {payload.get('type')}")

    return payload


# --- 일회성 토큰 (비밀번호 재설정 등) ---
def generate_secure_token(num_bytes: int = 32) -> str:
    """URL-safe 랜덤 토큰 생성 — 비밀번호 재설정 등 일회성 용도."""
    return secrets.token_urlsafe(num_bytes)
