"""구조화된 모니터링 서비스 (v0.6).

- structlog 기반 구조화 로깅
- API 레이턴시 추적
- LLM 호출 성공/실패/비용 메트릭
- RAG 검색 성능 측정
- WebSocket 연결 추적
- 사용자 행동 이벤트 분석
- OpenTelemetry 트레이싱 통합
"""

from __future__ import annotations

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone

import structlog

from app.core.config import settings

logger = logging.getLogger(__name__)

# === ContextVar for request tracing ===
_request_id: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(rid: str) -> None:
    _request_id.set(rid)


# === Structlog 설정 ===

def setup_structlog() -> None:
    """structlog 초기화 — main.py에서 호출."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.env == "production":
        # 프로덕션: JSON 출력 (ELK/CloudWatch 연동)
        renderer = structlog.processors.JSONRenderer()
    else:
        # 개발: 컬러 콘솔
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # stdlib logging도 structlog 포맷터로 통합
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=renderer,
        foreign_pre_chain=shared_processors,
    )

    root_handler = logging.StreamHandler()
    root_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(root_handler)
    root_logger.setLevel(settings.log_level)


def get_structured_logger(name: str) -> structlog.stdlib.BoundLogger:
    """모듈별 구조화 로거 반환."""
    return structlog.get_logger(name)


# === 메트릭 수집기 ===


@dataclass
class MetricsCollector:
    """인메모리 메트릭 수집 (Redis 백엔드로 확장 가능)."""

    api_latencies: list[dict] = field(default_factory=list)
    llm_calls: list[dict] = field(default_factory=list)
    rag_searches: list[dict] = field(default_factory=list)
    ws_connections: dict[str, int] = field(default_factory=lambda: {"active": 0, "total": 0, "disconnects": 0})
    user_events: list[dict] = field(default_factory=list)

    _MAX_BUFFER = 10000

    def record_api_latency(
        self, method: str, path: str, status_code: int, latency_ms: float,
        user_id: str | None = None,
    ) -> None:
        """API 요청 레이턴시 기록."""
        entry = {
            "method": method,
            "path": path,
            "status_code": status_code,
            "latency_ms": latency_ms,
            "user_id": user_id,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        self.api_latencies.append(entry)
        if len(self.api_latencies) > self._MAX_BUFFER:
            self.api_latencies = self.api_latencies[-self._MAX_BUFFER // 2:]

    def record_llm_call(
        self, provider: str, model: str, success: bool,
        input_tokens: int, output_tokens: int, latency_ms: int,
        cost_usd: float = 0.0,
    ) -> None:
        """LLM 호출 메트릭 기록."""
        self.llm_calls.append({
            "provider": provider,
            "model": model,
            "success": success,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
            "cost_usd": cost_usd,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.llm_calls) > self._MAX_BUFFER:
            self.llm_calls = self.llm_calls[-self._MAX_BUFFER // 2:]

    def record_rag_search(
        self, query_length: int, results_count: int,
        latency_ms: float, department: str | None = None,
    ) -> None:
        """RAG 검색 성능 기록."""
        self.rag_searches.append({
            "query_length": query_length,
            "results_count": results_count,
            "latency_ms": latency_ms,
            "department": department,
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.rag_searches) > self._MAX_BUFFER:
            self.rag_searches = self.rag_searches[-self._MAX_BUFFER // 2:]

    def ws_connect(self) -> None:
        self.ws_connections["active"] += 1
        self.ws_connections["total"] += 1

    def ws_disconnect(self) -> None:
        self.ws_connections["active"] = max(0, self.ws_connections["active"] - 1)
        self.ws_connections["disconnects"] += 1

    def record_user_event(
        self, user_id: str, event_type: str, detail: dict | None = None,
    ) -> None:
        """사용자 행동 이벤트 기록."""
        self.user_events.append({
            "user_id": user_id,
            "event_type": event_type,
            "detail": detail or {},
            "ts": datetime.now(timezone.utc).isoformat(),
        })
        if len(self.user_events) > self._MAX_BUFFER:
            self.user_events = self.user_events[-self._MAX_BUFFER // 2:]

    def get_summary(self) -> dict:
        """현재 메트릭 요약."""
        recent_api = self.api_latencies[-100:] if self.api_latencies else []
        recent_llm = self.llm_calls[-100:] if self.llm_calls else []
        recent_rag = self.rag_searches[-100:] if self.rag_searches else []

        api_latencies_ms = [e["latency_ms"] for e in recent_api]
        llm_latencies_ms = [e["latency_ms"] for e in recent_llm]
        rag_latencies_ms = [e["latency_ms"] for e in recent_rag]

        return {
            "api": {
                "total_requests": len(self.api_latencies),
                "recent_avg_ms": sum(api_latencies_ms) / len(api_latencies_ms) if api_latencies_ms else 0,
                "recent_p95_ms": sorted(api_latencies_ms)[int(len(api_latencies_ms) * 0.95)] if len(api_latencies_ms) > 1 else 0,
                "error_rate": sum(1 for e in recent_api if e["status_code"] >= 500) / len(recent_api) if recent_api else 0,
            },
            "llm": {
                "total_calls": len(self.llm_calls),
                "success_rate": sum(1 for e in recent_llm if e["success"]) / len(recent_llm) if recent_llm else 0,
                "recent_avg_ms": sum(llm_latencies_ms) / len(llm_latencies_ms) if llm_latencies_ms else 0,
                "total_cost_usd": sum(e.get("cost_usd", 0) for e in self.llm_calls),
            },
            "rag": {
                "total_searches": len(self.rag_searches),
                "recent_avg_ms": sum(rag_latencies_ms) / len(rag_latencies_ms) if rag_latencies_ms else 0,
                "avg_results": sum(e["results_count"] for e in recent_rag) / len(recent_rag) if recent_rag else 0,
            },
            "websocket": self.ws_connections.copy(),
            "user_events": {
                "total": len(self.user_events),
            },
        }


# === 싱글톤 ===
_metrics: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    """프로세스 단위 메트릭 수집기."""
    global _metrics
    if _metrics is None:
        _metrics = MetricsCollector()
    return _metrics


# === OpenTelemetry 설정 ===


def setup_opentelemetry(app) -> None:
    """OpenTelemetry 계측 초기화.

    OTEL_EXPORTER_OTLP_ENDPOINT 환경변수가 설정되어 있을 때만 활성화.
    """
    import os
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": "campuson-api", "service.version": "0.6"})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        FastAPIInstrumentor.instrument_app(app)
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()

        logger.info("✅ OpenTelemetry initialized → %s", endpoint)
    except ImportError:
        logger.warning("OpenTelemetry packages not installed, skipping")
    except Exception as exc:
        logger.warning("OpenTelemetry setup failed: %s", exc)


# === Sentry 설정 ===


def setup_sentry() -> None:
    """Sentry 에러 모니터링 초기화.

    SENTRY_DSN 환경변수가 설정되어 있을 때만 활성화.
    """
    import os
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("Sentry disabled (SENTRY_DSN not set)")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.env,
            traces_sample_rate=0.1 if settings.env == "production" else 1.0,
            profiles_sample_rate=0.1,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            send_default_pii=False,
        )
        logger.info("✅ Sentry initialized")
    except ImportError:
        logger.warning("sentry-sdk not installed, skipping")
    except Exception as exc:
        logger.warning("Sentry setup failed: %s", exc)
