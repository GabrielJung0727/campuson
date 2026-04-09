"""Audit log 서비스 — 민감 필드 마스킹 및 DB 저장."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

# 마스킹 대상 키 (대소문자 무시)
SENSITIVE_KEYS = {
    "password",
    "current_password",
    "new_password",
    "password_hash",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "authorization",
}

MASK = "***REDACTED***"
MAX_BODY_SIZE = 10_000  # 10 KB


def mask_sensitive(data: Any) -> Any:
    """JSON-like 데이터에서 민감 키 값을 마스킹."""
    if isinstance(data, dict):
        return {
            k: (MASK if k.lower() in SENSITIVE_KEYS else mask_sensitive(v)) for k, v in data.items()
        }
    if isinstance(data, list):
        return [mask_sensitive(item) for item in data]
    return data


def parse_request_body(raw: bytes | None) -> dict | None:
    """원시 요청 바디를 JSON 객체로 파싱하고 마스킹.

    JSON이 아니거나 파싱 실패 시 None을 반환한다.
    너무 큰 바디는 잘라낸다.
    """
    if not raw:
        return None
    if len(raw) > MAX_BODY_SIZE:
        return {"_truncated": True, "_size_bytes": len(raw)}
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None

    masked = mask_sensitive(parsed)
    return masked if isinstance(masked, dict) else {"_value": masked}


async def create_audit_log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None,
    user_role: str | None,
    ip_address: str | None,
    user_agent: str | None,
    method: str,
    path: str,
    query_string: str | None,
    request_body: dict | None,
    status_code: int,
    latency_ms: int,
    error_message: str | None = None,
) -> None:
    """감사 로그 1건 저장 — 미들웨어가 호출."""
    log = AuditLog(
        user_id=user_id,
        user_role=user_role,
        ip_address=ip_address,
        user_agent=(user_agent[:500] if user_agent else None),
        method=method,
        path=path[:500],
        query_string=(query_string[:2000] if query_string else None),
        request_body=request_body,
        status_code=status_code,
        latency_ms=latency_ms,
        error_message=(error_message[:1000] if error_message else None),
    )
    db.add(log)
    try:
        await db.commit()
    except Exception:
        # audit 로그 실패가 메인 요청을 막으면 안 됨
        await db.rollback()
        logger.exception("Failed to write audit log: %s %s", method, path)
