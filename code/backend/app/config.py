"""Настройки приложения из переменных окружения (.env)."""
from functools import lru_cache
from pathlib import Path

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
    # Базовый каталог рабочих файлов (должен совпадать с worker для upload → chain)
    work_dir: Path = Path("/tmp/ferag")
    # Redis (pub/sub для WebSocket статусов задач; тот же инстанс, что и Celery broker)
    redis_url: str = "redis://localhost:6379/0"
    # LLM для RAG-чата (LM Studio или OpenAI-совместимый)
    llm_api_url: str = "http://host.docker.internal:41234/v1"
    llm_model: str = "lmstudio-community/Meta-Llama-3.3-70B-Instruct-UDLQ4_K_M"


@lru_cache
def get_settings() -> Settings:
    """Синглтон настроек (кэш по умолчанию без аргументов)."""
    return Settings()
