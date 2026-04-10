"""User 관련 Pydantic 스키마."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import (
    AdminRole,
    Department,
    ProfessorRole,
    Role,
    StudentNationality,
    UserStatus,
)


class UserBase(BaseModel):
    """User 공통 필드."""

    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)
    department: Department


class UserPublic(UserBase):
    """다른 사용자에게 노출 가능한 안전한 표현 (password_hash 제외)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_no: str | None = None
    role: Role
    status: UserStatus
    professor_role: ProfessorRole | None = None
    admin_role: AdminRole | None = None
    nationality: StudentNationality | None = None
    grade: int | None = None
    created_at: datetime
    last_login_at: datetime | None = None


class UserMe(UserPublic):
    """본인 조회 응답 — 추가 필드를 포함할 수 있음."""

    updated_at: datetime
