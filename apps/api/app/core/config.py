"""애플리케이션 설정 — 환경 변수 로딩."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """`.env` 파일과 환경 변수에서 설정을 로드합니다."""

    model_config = SettingsConfigDict(
        env_file=".env",
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

    @property
    def cors_origin_list(self) -> list[str]:
        """쉼표 구분 문자열을 리스트로 변환."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """캐시된 설정 인스턴스를 반환합니다."""
    return Settings()


settings = get_settings()
