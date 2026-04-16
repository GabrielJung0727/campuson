"""FastAPI 애플리케이션 엔트리포인트."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.ai import router as ai_router
from app.api.announcements import router as announcements_router
from app.api.practicum import router as practicum_router
from app.api.practicum_ws import router as practicum_ws_router
from app.api.assignments import router as assignments_router
from app.api.auth import router as auth_router
from app.api.classes import router as classes_router
from app.api.diagnostic import router as diagnostic_router
from app.api.health import router as health_router
from app.api.kb import router as kb_router
from app.api.learning_history import router as learning_history_router
from app.api.password_reset import router as password_reset_router
from app.api.question_reviews import router as question_reviews_router
from app.api.questions import router as questions_router
from app.api.recommendation import router as recommendation_router
from app.api.stats import router as stats_router
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


API_DESCRIPTION = """
**CampusON** — 경복대학교 보건계열(간호·물리치료·치위생) 학생을 위한
**AI 학습튜터링 플랫폼** 백엔드 API입니다.

## 핵심 기능
- 🔐 **Auth/RBAC** — JWT + 4단계 역할(STUDENT/PROFESSOR/ADMIN/DEVELOPER)
- 📝 **문제은행** — 학과별 CRUD + 태그/필터 검색 + CSV 일괄 업로드
- 🧪 **진단 테스트** — 학과별 30문항 자동 출제 + 채점 + 취약영역 추출
- 📊 **학습 이력** — 풀이 채점 + 오답 자동 분류 + 오답노트 + 통계
- 🤖 **AI 튜터** — LLM Gateway(Anthropic/OpenAI/Mock) + 4종 프롬프트 템플릿

## 인증
대부분의 엔드포인트는 `Authorization: Bearer <access_token>` 헤더가 필요합니다.
토큰은 `POST /api/v1/auth/register` 또는 `POST /api/v1/auth/login`으로 발급받습니다.

## 권한 체계
- **STUDENT** — 본인 데이터만 열람/생성
- **PROFESSOR** — 본인 학과 학생 데이터 열람
- **ADMIN** — 학교 단위 운영 데이터, 문제은행 관리
- **DEVELOPER** — 전체 + 시스템 로그/AI 호출 감사
""".strip()

TAGS_METADATA = [
    {"name": "health", "description": "헬스체크 (livenes/readiness)"},
    {"name": "auth", "description": "회원가입/로그인/토큰/비밀번호 재설정"},
    {"name": "users", "description": "사용자 정보 조회/변경 (RBAC 적용)"},
    {"name": "questions", "description": "문제은행 CRUD + 태그/필터 검색 + CSV 업로드"},
    {
        "name": "diagnostic",
        "description": "진단 테스트 (1회 제한) + AI 프로파일 자동 생성",
    },
    {
        "name": "learning-history",
        "description": "풀이 채점/저장 + 오답 자동 분류 + 오답노트 + 학습 통계",
    },
    {
        "name": "ai",
        "description": "LLM 기반 문제 해설/QA + 호출 감사 로그 (Day 6)",
    },
    {
        "name": "kb",
        "description": "지식베이스 적재/검수/하이브리드 검색 (Day 8~9 RAG)",
    },
    {
        "name": "recommendation",
        "description": "학습 추천 문제 세트 (Day 11 추천 엔진)",
    },
]


app = FastAPI(
    title="CampusON API",
    description=API_DESCRIPTION,
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.api_prefix}/openapi.json",
    openapi_tags=TAGS_METADATA,
    contact={
        "name": "CampusON Team",
        "url": "https://www.notion.so/CampusON-AI-33d3748c8e9e80de8a5ccf9e72a350b6",
    },
    license_info={"name": "Proprietary (경복대학교)"},
    swagger_ui_parameters={"persistAuthorization": True, "displayRequestDuration": True},
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
app.include_router(kb_router, prefix=settings.api_prefix)
app.include_router(recommendation_router, prefix=settings.api_prefix)
app.include_router(stats_router, prefix=settings.api_prefix)
app.include_router(classes_router, prefix=settings.api_prefix)
app.include_router(assignments_router, prefix=settings.api_prefix)
app.include_router(announcements_router, prefix=settings.api_prefix)
app.include_router(practicum_router, prefix=settings.api_prefix)
app.include_router(practicum_ws_router, prefix=settings.api_prefix)
app.include_router(question_reviews_router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict[str, str]:
    """루트 — 간단한 환영 메시지."""
    return {
        "service": "CampusON API",
        "version": __version__,
        "docs": "/docs",
        "health": f"{settings.api_prefix}/health",
    }
