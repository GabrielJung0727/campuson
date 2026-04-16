"""모니터링 미들웨어 — API 레이턴시 추적 + 구조화 로깅 (v0.6)."""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.services.monitoring import get_metrics, get_structured_logger, set_request_id

logger = get_structured_logger("campuson.api")


class MonitoringMiddleware(BaseHTTPMiddleware):
    """API 레이턴시 + 구조화 로깅 미들웨어.

    AuditLogMiddleware와 별개로, 순수 성능/관찰용 데이터를 수집한다.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid.uuid4())[:8]
        set_request_id(request_id)

        start = time.monotonic()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        finally:
            latency_ms = (time.monotonic() - start) * 1000
            status_code = response.status_code if response else 500
            method = request.method
            path = request.url.path

            # 메트릭 수집
            user_id = None
            if hasattr(request.state, "user_id"):
                user_id = str(request.state.user_id)

            metrics = get_metrics()
            metrics.record_api_latency(
                method=method, path=path,
                status_code=status_code, latency_ms=latency_ms,
                user_id=user_id,
            )

            # 구조화 로깅
            log_data = {
                "request_id": request_id,
                "method": method,
                "path": path,
                "status": status_code,
                "latency_ms": round(latency_ms, 1),
            }
            if user_id:
                log_data["user_id"] = user_id

            if status_code >= 500:
                logger.error("request_failed", **log_data)
            elif status_code >= 400:
                logger.warning("request_error", **log_data)
            elif latency_ms > 5000:
                logger.warning("slow_request", **log_data)
            # else: too verbose for normal requests
