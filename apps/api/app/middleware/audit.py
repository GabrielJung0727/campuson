"""Audit log 미들웨어 — 모든 API 요청을 비동기로 기록.

특징
----
- 요청 바디를 안전하게 한 번 읽고 다시 주입 (FastAPI/Starlette body 재사용 패턴)
- 민감 필드 자동 마스킹 (services.audit_service.mask_sensitive)
- audit 로그 실패는 메인 응답을 막지 않음
- skip 경로(헬스체크, 문서 등) 설정 가능
- JWT 토큰을 best-effort로 디코딩하여 user_id/role을 기록 (auth dependency 호출 전)
"""

import logging
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Message

from app.core.config import settings
from app.core.security import TokenError, decode_token
from app.db.session import AsyncSessionLocal
from app.services.audit_service import create_audit_log, parse_request_body

logger = logging.getLogger(__name__)


class AuditLogMiddleware(BaseHTTPMiddleware):
    """모든 HTTP 요청에 대한 감사 로그 기록."""

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        if not settings.audit_log_enabled or request.url.path in settings.audit_log_skip_path_set:
            return await call_next(request)

        start = time.monotonic()

        # --- 요청 바디 캡처 (한 번만 읽고 재주입) ---
        body_bytes: bytes | None = None
        if request.method in {"POST", "PUT", "PATCH"}:
            body_bytes = await request.body()

            async def receive() -> Message:
                return {"type": "http.request", "body": body_bytes, "more_body": False}

            request._receive = receive  # type: ignore[attr-defined]

        # --- 인증 정보 추출 (best-effort) ---
        user_id, user_role = _extract_user_from_token(request.headers.get("Authorization"))

        error_message: str | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_message = repr(exc)[:1000]
            status_code = 500
            logger.exception("Unhandled exception in request: %s %s", request.method, request.url.path)
            raise
        finally:
            latency_ms = int((time.monotonic() - start) * 1000)

            # 감사 로그 기록 — 별도 세션 사용 (요청 트랜잭션과 분리)
            try:
                parsed_body = parse_request_body(body_bytes)
                async with AsyncSessionLocal() as audit_db:
                    await create_audit_log(
                        audit_db,
                        user_id=user_id,
                        user_role=user_role,
                        ip_address=_get_client_ip(request),
                        user_agent=request.headers.get("User-Agent"),
                        method=request.method,
                        path=request.url.path,
                        query_string=str(request.url.query) or None,
                        request_body=parsed_body,
                        status_code=status_code,
                        latency_ms=latency_ms,
                        error_message=error_message,
                    )
            except Exception:  # noqa: BLE001
                logger.exception("Audit log middleware failed silently")

        return response


def _extract_user_from_token(
    authorization_header: str | None,
) -> tuple[uuid.UUID | None, str | None]:
    """Authorization 헤더에서 user_id/role을 best-effort로 추출."""
    if not authorization_header or not authorization_header.lower().startswith("bearer "):
        return None, None
    token = authorization_header.split(" ", 1)[1].strip()
    try:
        payload = decode_token(token, expected_type="access")
    except TokenError:
        return None, None

    sub = payload.get("sub")
    role = payload.get("role")
    try:
        user_id = uuid.UUID(sub) if sub else None
    except (ValueError, TypeError):
        user_id = None
    return user_id, role


def _get_client_ip(request: Request) -> str | None:
    """프록시 헤더를 고려한 클라이언트 IP 추출."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else None
