"""Day 2 보안 모듈 단위 테스트."""

from __future__ import annotations

import pytest

from app.core.security import (
    PasswordPolicyError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_policy,
    verify_password,
)


class TestPasswordPolicy:
    def test_valid(self) -> None:
        validate_password_policy("Test1234")  # 영문 + 숫자 + 8자

    def test_too_short(self) -> None:
        with pytest.raises(PasswordPolicyError, match="최소"):
            validate_password_policy("Tt1")

    def test_no_letter(self) -> None:
        with pytest.raises(PasswordPolicyError, match="영문자"):
            validate_password_policy("12345678")

    def test_no_digit(self) -> None:
        with pytest.raises(PasswordPolicyError, match="숫자"):
            validate_password_policy("abcdefgh")

    def test_with_space(self) -> None:
        with pytest.raises(PasswordPolicyError, match="공백"):
            validate_password_policy("Test 1234")


class TestPasswordHashing:
    def test_hash_and_verify(self) -> None:
        h = hash_password("Test1234")
        assert h != "Test1234"
        assert verify_password("Test1234", h)
        assert not verify_password("Wrong1234", h)


class TestJWT:
    def test_access_token_roundtrip(self) -> None:
        token = create_access_token("user-123", extra_claims={"role": "STUDENT"})
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == "user-123"
        assert payload["type"] == "access"
        assert payload["role"] == "STUDENT"

    def test_refresh_token_roundtrip(self) -> None:
        token = create_refresh_token("user-456")
        payload = decode_token(token, expected_type="refresh")
        assert payload["sub"] == "user-456"
        assert payload["type"] == "refresh"

    def test_wrong_type_rejected(self) -> None:
        from app.core.security import TokenError

        access = create_access_token("u")
        with pytest.raises(TokenError):
            decode_token(access, expected_type="refresh")
