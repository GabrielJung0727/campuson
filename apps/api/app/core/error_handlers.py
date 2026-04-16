"""통합 에러 응답 포맷 — 전역 예외 핸들러 (v0.9).

모든 에러를 일관된 JSON 형식으로 반환:
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Human-readable message",
        "details": [...],   # optional
        "request_id": "..."  # optional trace id
    }
}
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# === Error codes ===

class ErrorCode:
    """표준 에러 코드 상수."""
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    CONFLICT = "CONFLICT"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    BAD_REQUEST = "BAD_REQUEST"


# HTTP status → error code 매핑
_STATUS_TO_CODE: dict[int, str] = {
    400: ErrorCode.BAD_REQUEST,
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    422: ErrorCode.VALIDATION_ERROR,
    429: ErrorCode.RATE_LIMITED,
    500: ErrorCode.INTERNAL_ERROR,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


# === Schemas ===


class ErrorDetail(BaseModel):
    """개별 validation 에러 상세."""
    field: str
    message: str
    type: str | None = None


class ErrorBody(BaseModel):
    """통합 에러 응답 본문."""
    code: str
    message: str
    details: list[ErrorDetail] | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """최상위 에러 응답 래퍼."""
    error: ErrorBody


# === Handlers ===


def _get_request_id(request: Request) -> str:
    """요청 ID 추출 또는 생성."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """FastAPI/Starlette HTTPException 통합 핸들러."""
    code = _STATUS_TO_CODE.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
    message = exc.detail if isinstance(exc.detail, str) else str(exc.detail)

    body = ErrorResponse(
        error=ErrorBody(
            code=code,
            message=message,
            request_id=_get_request_id(request),
        )
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=body.model_dump(exclude_none=True),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError,
) -> JSONResponse:
    """Pydantic 유효성 검증 실패 핸들러."""
    details = []
    for err in exc.errors():
        loc = err.get("loc", ())
        field = ".".join(str(l) for l in loc if l != "body")
        details.append(ErrorDetail(
            field=field or "unknown",
            message=err.get("msg", ""),
            type=err.get("type"),
        ))

    body = ErrorResponse(
        error=ErrorBody(
            code=ErrorCode.VALIDATION_ERROR,
            message=f"Validation failed: {len(details)} error(s)",
            details=details,
            request_id=_get_request_id(request),
        )
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=body.model_dump(exclude_none=True),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """예상치 못한 예외 핸들러 — 500 반환."""
    request_id = _get_request_id(request)
    logger.exception("Unhandled exception [request_id=%s]: %s", request_id, exc)

    body = ErrorResponse(
        error=ErrorBody(
            code=ErrorCode.INTERNAL_ERROR,
            message="An unexpected error occurred",
            request_id=request_id,
        )
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=body.model_dump(exclude_none=True),
    )


def register_error_handlers(app: FastAPI) -> None:
    """앱에 전역 에러 핸들러를 등록합니다."""
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
