"""공통 스키마 — 에러 응답, 페이지네이션 등."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """표준 에러 응답."""

    detail: str = Field(..., description="에러 상세 메시지")


class MessageResponse(BaseModel):
    """단순 메시지 응답."""

    message: str
