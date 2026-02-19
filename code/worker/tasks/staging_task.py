"""Celery-задача: загрузка integrated_*.ttl в staging датасеты Fuseki, UploadCycle.status='review'."""
from pathlib import Path

from worker.celery_app import celery
from worker.config import get_settings
from worker.fuseki_client import (
    create_dataset,
    load_ttl_into_dataset,
    rag_ontology_dataset,
    rag_staging_dataset,
    rag_triples_dataset,
)
from worker.tasks.base import (
    get_cycle_n,
    get_db_session,
    get_redis,
    publish_status,
    update_task,
    update_upload_cycle_status,
)


@celery.task(
    bind=True,
    name="worker.tasks.staging_task.load_to_staging",
    time_limit=3600,
    soft_time_limit=3600,
)
def load_to_staging(
    self,
    rag_id: int,
    cycle_id: int,
    task_id: int,
):
    """
    Создать датасеты -triples, -ontology, -staging; загрузить integrated_triples.ttl → -tri,
    integrated_ontology.ttl → -ont; UploadCycle.status='review', Task.status='done', publish done.
    При ошибке — update_task(failed), publish_status(failed), raise.
    """
    settings = get_settings()
    work_dir = Path(settings.work_dir) / f"rag_{rag_id}" / f"cycle_{cycle_id}"
    r = get_redis()
    db = get_db_session()

    try:
        publish_status(r, task_id, "running", "staging", None)

        cycle_n = get_cycle_n(db, cycle_id)
        ds_tri = rag_triples_dataset(rag_id, cycle_n)
        ds_ont = rag_ontology_dataset(rag_id, cycle_n)
        ds_stg = rag_staging_dataset(rag_id, cycle_n)

        create_dataset(ds_tri)
        create_dataset(ds_ont)
        create_dataset(ds_stg)

        load_ttl_into_dataset(ds_tri, work_dir / "integrated_triples.ttl")
        load_ttl_into_dataset(ds_ont, work_dir / "integrated_ontology.ttl")

        update_upload_cycle_status(db, cycle_id, "review")
        update_task(db, task_id, "done", None)
        publish_status(r, task_id, "done", "staging", None)
    except Exception as e:
        err_msg = str(e)
        update_task(db, task_id, "failed", err_msg)
        publish_status(r, task_id, "failed", "staging", err_msg)
        db.close()
        raise
    finally:
        db.close()
