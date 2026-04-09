"""FastAPI 애플리케이션 엔트리포인트."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.health import router as health_router
from app.core.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 시작/종료 훅."""
    # Startup
    print(f"🚀 CampusON API v{__version__} starting in {settings.env} mode")
    yield
    # Shutdown
    print("👋 CampusON API shutting down")


app = FastAPI(
    title="CampusON API",
    description="경복대학교 보건계열 AI 학습튜터링 플랫폼 백엔드",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    lifespan=lifespan,
)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Routers ---
app.include_router(health_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """루트 — 간단한 환영 메시지."""
    return {
        "service": "CampusON API",
        "version": __version__,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
