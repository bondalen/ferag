"""Настройки worker из переменных окружения (.env). Аналогично backend: BaseSettings, загрузка из .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Конфигурация worker из .env / env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Celery
    celery_broker_url: str
    celery_result_backend: str
    # БД
    database_url: str
    # Fuseki
    fuseki_url: str
    fuseki_user: str
    fuseki_password: str
    # LLM (LM Studio или OpenAI-совместимый)
    llm_api_url: str = "http://host.docker.internal:41234/v1"
    llm_model: str = "lmstudio-community/Meta-Llama-3.3-70B-Instruct-UDLQ4_K_M"
    # Базовый каталог рабочих файлов циклов
    work_dir: Path = Path("/tmp/ferag")
    # Каталог graphrag-test (шаблоны settings, prompts) — в Docker: /app/graphrag-test
    graphrag_test_dir: Path = Path("/app/graphrag-test")


@lru_cache
def get_settings() -> Settings:
    """Синглтон настроек."""
    return Settings()
