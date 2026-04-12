"""인증 관련 Pydantic 스키마 — 회원가입/로그인/토큰/비밀번호 재설정."""

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import Department, Role
from app.schemas.user import UserPublic


class RegisterRequest(BaseModel):
    """회원가입 요청.

    학번(student_no)은 학생만 필수, 교수/관리자는 NULL 가능.
    실제 가입 정책은 서비스 레이어에서 검증.
    """

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=50)
    department: Department
    role: Role = Role.STUDENT
    student_no: str | None = Field(
        default=None,
        description="학생만 해당. 8~10자리 숫자",
        examples=["24001234"],
    )


class LoginRequest(BaseModel):
    """이메일/비밀번호 로그인 요청."""

    email: EmailStr
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    """액세스/리프레시 토큰 + 사용자 정보 응답."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserPublic


class RefreshTokenRequest(BaseModel):
    """토큰 재발급 요청."""

    refresh_token: str


class AccessTokenResponse(BaseModel):
    """액세스 토큰만 반환 (refresh 시 사용)."""

    access_token: str
    token_type: str = "bearer"


class PasswordResetRequest(BaseModel):
    """비밀번호 재설정 요청 — 이메일만 받음 (사용자 존재 여부 노출 방지)."""

    email: EmailStr


class PasswordResetConfirm(BaseModel):
    """비밀번호 재설정 확인 — 토큰 + 새 비밀번호."""

    token: str = Field(..., min_length=10)
    new_password: str = Field(..., min_length=8, max_length=128)


class PasswordChangeRequest(BaseModel):
    """로그인 상태에서 비밀번호 변경."""

    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)


class VerifyEmailRequest(BaseModel):
    """이메일 인증코드 검증."""

    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$")


class ResendVerificationRequest(BaseModel):
    """인증코드 재발송 요청."""

    email: EmailStr


class RegisterResponse(BaseModel):
    """회원가입 응답 — 이메일 인증이 필요한 경우."""

    message: str
    user_id: str
    email: str
    requires_verification: bool = True


class FindEmailRequest(BaseModel):
    """아이디(이메일) 찾기 — 이름 + 학번으로 조회."""

    name: str = Field(..., min_length=1, max_length=50)
    student_no: str = Field(..., min_length=7, max_length=10)
