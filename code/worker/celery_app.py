"""Celery app для ferag worker (GraphRAG pipeline, staging)."""
from celery import Celery

from worker.config import get_settings

settings = get_settings()

celery = Celery(
    "ferag_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "worker.tasks",
        "worker.tasks.graphrag_task",
        "worker.tasks.schema_task",
        "worker.tasks.merge_task",
        "worker.tasks.staging_task",
    ],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
)
