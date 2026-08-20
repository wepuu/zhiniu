from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "zhaoniu"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://zhaoniu:zhaoniu@localhost:5432/zhaoniu"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    auth_cookie_name: str = "zhaoniu_session"
    auth_csrf_cookie_name: str = "zhaoniu_csrf"
    auth_cookie_secure: bool = False
    allowed_origins: str = "http://localhost:3000"
    auth_session_days: int = Field(default=30, ge=1, le=90)
    auth_password_min_length: int = Field(default=15, ge=15, le=128)
    market_data_provider: Literal["akshare"] = "akshare"
    disclosure_provider: Literal["akshare"] = "akshare"
    llm_enabled: bool = False
    llm_model_chain: str = ""
    llm_max_attempts: int = Field(default=4, ge=1, le=4)
    llm_per_model_timeout_seconds: float = Field(default=75, gt=0, le=180)
    llm_run_deadline_seconds: float = Field(default=240, gt=0, le=600)
    screen_parser_enabled: bool = False
    screen_parser_model_chain: str = ""
    screen_parser_max_attempts: int = Field(default=2, ge=1, le=2)
    screen_parser_per_model_timeout_seconds: float = Field(default=30, gt=0, le=60)
    screen_parser_run_deadline_seconds: float = Field(default=75, gt=0, le=120)
    screen_parser_hmac_secret: str = "development-only-change-me"
    screen_parser_input_ttl_seconds: int = Field(default=600, ge=60, le=1800)

    @property
    def llm_models(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.llm_model_chain.split(",") if item.strip())

    @property
    def screen_parser_models(self) -> tuple[str, ...]:
        return tuple(
            item.strip() for item in self.screen_parser_model_chain.split(",") if item.strip()
        )

    @property
    def origin_allowlist(self) -> tuple[str, ...]:
        return tuple(
            item.strip().rstrip("/") for item in self.allowed_origins.split(",") if item.strip()
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
