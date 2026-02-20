"""Отправка Celery-цепочки обновления RAG по имени задачи (без импорта worker-пакета)."""
from celery import Celery, chain

from app.config import get_settings


def _get_celery() -> Celery:
    s = get_settings()
    return Celery(broker=s.celery_broker_url, backend=s.celery_result_backend)


def send_update_chain(rag_id: int, cycle_id: int, task_id: int, input_file: str) -> None:
    """Запустить цепочку: run_graphrag → run_schema_induction → do_merge → load_to_staging."""
    app = _get_celery()
    chain(
        app.signature(
            "worker.tasks.graphrag_task.run_graphrag",
            args=[rag_id, cycle_id, task_id, input_file],
        ),
        app.signature(
            "worker.tasks.schema_task.run_schema_induction",
            args=[rag_id, cycle_id, task_id],
            immutable=True,
        ),
        app.signature(
            "worker.tasks.merge_task.do_merge",
            args=[rag_id, cycle_id, task_id],
            immutable=True,
        ),
        app.signature(
            "worker.tasks.staging_task.load_to_staging",
            args=[rag_id, cycle_id, task_id],
            immutable=True,
        ),
    ).apply_async()
