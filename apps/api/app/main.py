"""FastAPI 애플리케이션 엔트리포인트."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.diagnostic import router as diagnostic_router
from app.api.health import router as health_router
from app.api.learning_history import router as learning_history_router
from app.api.password_reset import router as password_reset_router
from app.api.questions import router as questions_router
from app.api.users import router as users_router
from app.core.config import settings
from app.core.redis import close_redis, get_redis_client
from app.middleware import AuditLogMiddleware

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 훅."""
    # Startup
    logger.info("🚀 CampusON API v%s starting in %s mode", __version__, settings.env)
    # Redis ping (best-effort)
    try:
        redis = get_redis_client()
        await redis.ping()
        logger.info("✅ Redis connected")
    except Exception as exc:  # noqa: BLE001
        logger.warning("⚠️  Redis ping failed: %s", exc)

    yield

    # Shutdown
    logger.info("👋 CampusON API shutting down")
    await close_redis()


app = FastAPI(
    title="CampusON API",
    description="경복대학교 보건계열 AI 학습튜터링 플랫폼 백엔드",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)

# --- Middleware (역순으로 등록 — 마지막에 등록한 것이 가장 바깥) ---
# CORS는 가장 바깥쪽에 두는 것이 일반적
app.add_middleware(AuditLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health_router, prefix=settings.api_prefix)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(password_reset_router, prefix=settings.api_prefix)
app.include_router(users_router, prefix=settings.api_prefix)
app.include_router(questions_router, prefix=settings.api_prefix)
app.include_router(diagnostic_router, prefix=settings.api_prefix)
app.include_router(learning_history_router, prefix=settings.api_prefix)
app.include_router(ai_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """루트 — 간단한 환영 메시지."""
    return {
        "service": "CampusON API",
        "version": __version__,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
