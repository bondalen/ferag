"""Настройки приложения из переменных окружения (.env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация из .env / env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    fuseki_url: str
    fuseki_user: str
    fuseki_password: str


@lru_cache
def get_settings() -> Settings:
    """Синглтон настроек (кэш по умолчанию без аргументов)."""
    return Settings()
