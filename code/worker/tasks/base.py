"""Вспомогательные функции для задач: БД, Redis pub/sub, обновление Task."""
import json
from typing import Any, Optional, Tuple

import redis
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from worker.celery_app import celery
from worker.config import get_settings

_settings = get_settings()
_engine = create_engine(_settings.database_url)
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


def get_redis() -> redis.Redis:
    """Клиент Redis по CELERY_BROKER_URL (для pub/sub статусов)."""
    return redis.Redis.from_url(_settings.celery_broker_url, decode_responses=True)


def get_db_session() -> Session:
    """Создать сессию БД по DATABASE_URL."""
    return _SessionLocal()


def publish_status(
    r: redis.Redis,
    task_id: int,
    status: str,
    step: str,
    error: Optional[str] = None,
) -> None:
    """Опубликовать статус в Redis channel task:{task_id} для WebSocket."""
    channel = f"task:{task_id}"
    payload = {"status": status, "step": step, "error": error}
    r.publish(channel, json.dumps(payload))


def update_task(
    db: Session,
    task_id: int,
    status: str,
    error: Optional[str] = None,
) -> None:
    """Обновить запись Task в БД."""
    db.execute(
        text(
            "UPDATE tasks SET status = :status, error = :error, updated_at = now() WHERE id = :id"
        ),
        {"status": status, "error": error, "id": task_id},
    )
    db.commit()


def update_upload_cycle_status(db: Session, cycle_id: int, status: str) -> None:
    """Обновить status у UploadCycle по id (upload_cycles.id)."""
    db.execute(
        text(
            "UPDATE upload_cycles SET status = :status WHERE id = :id"
        ),
        {"status": status, "id": cycle_id},
    )
    db.commit()


def get_cycle_n(db: Session, cycle_id: int) -> int:
    """Вернуть cycle_n по id записи upload_cycles. Бросает ValueError, если запись не найдена."""
    row = db.execute(
        text("SELECT cycle_n FROM upload_cycles WHERE id = :id"),
        {"id": cycle_id},
    ).fetchone()
    if not row:
        raise ValueError(f"UploadCycle id={cycle_id} not found")
    return int(row[0])


@celery.task(name="worker.tasks.base.on_chain_failure")
def on_chain_failure(
    request: Any,
    exc: BaseException,
    traceback: Any,
) -> None:
    """
    Callback при падении любого шага цепочки: Task.status='failed', publish в Redis.
    Вызывается через link_error с аргументами (request, exc, traceback).
    request.args у всех шагов: (rag_id, cycle_id, task_id[, input_file]).
    """
    if not request or not getattr(request, "args", None) or len(request.args) < 3:
        return
    task_id = request.args[2]
    err_msg = str(exc) if exc else "Unknown error"
    db = get_db_session()
    try:
        update_task(db, task_id, "failed", err_msg)
        r = get_redis()
        publish_status(r, task_id, "failed", step="", error=err_msg)
    finally:
        db.close()
