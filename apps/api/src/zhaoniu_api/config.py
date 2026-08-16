from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "zhaoniu"
    app_env: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://zhaoniu:zhaoniu@localhost:5432/zhaoniu"
    redis_url: str = "redis://localhost:6379/0"
    auth_cookie_name: str = "zhaoniu_session"
    auth_cookie_secure: bool = False
    market_data_provider: str = "mock"


@lru_cache
def get_settings() -> Settings:
    return Settings()
