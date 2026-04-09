"""Pydantic 스키마 (request/response DTO)."""

from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    TokenResponse,
)
from app.schemas.common import ErrorResponse, MessageResponse
from app.schemas.diagnostic import (
    AIProfileResponse,
    DiagnosticAnswerInput,
    DiagnosticResultResponse,
    DiagnosticStartResponse,
    DiagnosticSubmitRequest,
    WeakAreaItem,
)
from app.schemas.question import (
    BulkUploadResult,
    QuestionCreate,
    QuestionListResponse,
    QuestionPublic,
    QuestionResponse,
    QuestionUpdate,
)
from app.schemas.user import UserBase, UserMe, UserPublic

__all__ = [
    "AIProfileResponse",
    "AccessTokenResponse",
    "BulkUploadResult",
    "DiagnosticAnswerInput",
    "DiagnosticResultResponse",
    "DiagnosticStartResponse",
    "DiagnosticSubmitRequest",
    "ErrorResponse",
    "LoginRequest",
    "MessageResponse",
    "PasswordChangeRequest",
    "PasswordResetConfirm",
    "PasswordResetRequest",
    "QuestionCreate",
    "QuestionListResponse",
    "QuestionPublic",
    "QuestionResponse",
    "QuestionUpdate",
    "RefreshTokenRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserBase",
    "UserMe",
    "UserPublic",
    "WeakAreaItem",
]
