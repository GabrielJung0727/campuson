"""pytest 공통 설정 — 환경 변수 셋업, DB fixture, HTTP client.

테스트 DB 정책
-------------
- 별도 DB(`campuson_test`)를 사용한다. CI에서는 GitHub Actions의 services로 띄움.
- 로컬에서는 docker-compose 의 PostgreSQL을 그대로 쓰되 `campuson_test` DB를 사용.
- 매 테스트 세션 시작에 모든 테이블을 drop → create_all로 깨끗한 상태 보장.
- 학과별 시드 문제 200문항을 자동 적재 (진단 테스트가 동작하기 위해 필요).
- LLM은 강제로 mock provider 사용.

환경 변수
--------
TEST_DATABASE_URL / TEST_DATABASE_URL_SYNC를 설정하면 그것을 사용,
없으면 기본값(`postgresql+asyncpg://campuson:campuson_dev_pw@localhost:5432/campuson_test`).

NOTE: conftest.py 는 다른 모든 import 보다 먼저 환경 변수를 설정해야 한다.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# === 1) 환경 변수 셋업 (반드시 app import 전) ===
_TEST_DB_ASYNC = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://campuson:campuson_dev_pw@localhost:5432/campuson_test",
)
_TEST_DB_SYNC = os.environ.get(
    "TEST_DATABASE_URL_SYNC",
    "postgresql+psycopg2://campuson:campuson_dev_pw@localhost:5432/campuson_test",
)

os.environ["DATABASE_URL"] = _TEST_DB_ASYNC
os.environ["DATABASE_URL_SYNC"] = _TEST_DB_SYNC
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ENV"] = "development"
os.environ["AUDIT_LOG_ENABLED"] = "false"  # 테스트 잡음 줄임
os.environ["JWT_SECRET_KEY"] = "test-secret-do-not-use-in-prod"

# apps/api 를 sys.path에 추가
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# === 2) 표준 import (반드시 환경 변수 셋업 후) ===
import asyncio  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app import models  # noqa: E402, F401  — 모든 모델 등록
from app.db.base import Base  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import Department, Difficulty, QuestionType  # noqa: E402
from app.models.question import Question  # noqa: E402
from scripts.seed_data.dental_hygiene import DH_QUESTIONS  # noqa: E402
from scripts.seed_data.nursing import NURSING_QUESTIONS  # noqa: E402
from scripts.seed_data.physical_therapy import PT_QUESTIONS  # noqa: E402

# === 3) 이벤트 루프 (session 스코프) ===


@pytest.fixture(scope="session")
def event_loop():
    """pytest-asyncio가 session-scoped fixture를 쓰려면 직접 loop를 만들어야 한다."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# === 4) 테스트 엔진 + 스키마 초기화 ===


@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """세션 단위 비동기 엔진. drop_all → create_all로 깨끗한 스키마 준비."""
    engine = create_async_engine(_TEST_DB_ASYNC, future=True, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def seeded_engine(test_engine) -> AsyncGenerator:
    """200문항 시드 + ready engine."""
    SessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        all_seed = (
            [(q, Department.NURSING) for q in NURSING_QUESTIONS]
            + [(q, Department.PHYSICAL_THERAPY) for q in PT_QUESTIONS]
            + [(q, Department.DENTAL_HYGIENE) for q in DH_QUESTIONS]
        )
        for payload, dept in all_seed:
            session.add(
                Question(
                    department=dept,
                    subject=payload["subject"],
                    unit=payload.get("unit"),
                    difficulty=payload.get("difficulty", Difficulty.MEDIUM),
                    question_type=payload.get(
                        "question_type", QuestionType.SINGLE_CHOICE
                    ),
                    question_text=payload["question_text"],
                    choices=payload["choices"],
                    correct_answer=payload["correct_answer"],
                    explanation=payload.get("explanation"),
                    tags=payload.get("tags", []),
                    source=payload.get("source", "test seed"),
                )
            )
        await session.commit()
    yield test_engine


# === 5) DB 세션 fixture (테스트별, app의 get_db를 override) ===


@pytest_asyncio.fixture
async def db_session(seeded_engine) -> AsyncGenerator[AsyncSession, None]:
    SessionLocal = async_sessionmaker(bind=seeded_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


# === 6) HTTP 클라이언트 (app override) ===


@pytest_asyncio.fixture
async def client(seeded_engine) -> AsyncGenerator[AsyncClient, None]:
    """앱의 get_db 의존성을 테스트 엔진으로 갈아끼운 AsyncClient."""
    from app.db.session import get_db

    SessionLocal = async_sessionmaker(bind=seeded_engine, expire_on_commit=False)

    async def _override_get_db():
        async with SessionLocal() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.pop(get_db, None)
