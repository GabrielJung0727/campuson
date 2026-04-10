"""애플리케이션 설정 — 환경 변수 로딩."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py
#   parents[0] = core/
#   parents[1] = app/
#   parents[2] = api/
#   parents[3] = apps/
#   parents[4] = campuson/ (repo root)
_REPO_ROOT = Path(__file__).resolve().parents[4]
_API_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """`.env` 파일과 환경 변수에서 설정을 로드합니다.

    env 파일 탐색 우선순위
    --------------------
    1. `apps/api/.env` (API 전용 override가 있을 경우)
    2. 프로젝트 루트 `campuson/.env` (기본 공유 설정)
    3. 현재 작업 디렉토리의 `.env` (pytest 등 fallback)
    """

    model_config = SettingsConfigDict(
        env_file=(
            _API_ROOT / ".env",
            _REPO_ROOT / ".env",
            ".env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- 환경 ---
    env: str = "development"
    debug: bool = True
    log_level: str = "INFO"

    # --- API ---
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    # --- Database ---
    database_url: str = Field(
        default="postgresql+asyncpg://campuson:campuson_dev_pw@localhost:5432/campuson"
    )
    database_url_sync: str = Field(
        default="postgresql+psycopg2://campuson:campuson_dev_pw@localhost:5432/campuson"
    )

    # --- Redis ---
    redis_url: str = "redis://:campuson_dev_pw@localhost:6379/0"

    # --- JWT (Day 2부터 사용) ---
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 14

    # --- Security ---
    bcrypt_rounds: int = 12
    password_min_length: int = 8
    password_reset_token_expire_minutes: int = 30
    audit_log_enabled: bool = True
    audit_log_skip_paths: str = "/,/docs,/redoc,/api/v1/openapi.json,/api/v1/health"

    # --- LLM (Day 6부터 사용) ---
    llm_provider: str = "mock"  # anthropic | openai | mock
    llm_model: str = "claude-sonnet-4-6"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.3
    llm_timeout_sec: float = 60.0
    llm_max_retries: int = 3
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # --- SMTP Email ---
    smtp_enabled: bool = False
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "CampusON"
    smtp_use_tls: bool = True
    email_verification_code_expire_minutes: int = 10

    # --- Embeddings (Day 8부터 사용) ---
    embedding_provider: str = "mock"  # openai | mock
    embedding_model: str = "text-embedding-3-small"
    # pgvector HNSW 인덱스 차원 제한(<=2000)에 맞춘 기본값.
    # text-embedding-3-large(3072)는 OpenAI `dimensions` 파라미터로 1536 축소 사용.
    embedding_dimensions: int = 1536
    embedding_batch_size: int = 96

    # --- Chunking (Day 8) ---
    chunk_target_tokens: int = 800
    chunk_overlap_tokens: int = 150
    chunk_min_tokens: int = 200
    chunk_max_tokens: int = 1200

    @property
    def cors_origin_list(self) -> list[str]:
        """쉼표 구분 문자열을 리스트로 변환."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def audit_log_skip_path_set(self) -> set[str]:
        """감사 로그 제외 경로 집합."""
        return {p.strip() for p in self.audit_log_skip_paths.split(",") if p.strip()}


@lru_cache
def get_settings() -> Settings:
    """캐시된 설정 인스턴스를 반환합니다."""
    return Settings()


settings = get_settings()
