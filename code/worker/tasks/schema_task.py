"""Celery-задача: Schema Induction → extracted_ontology.ttl."""
import sys
from pathlib import Path

from worker.celery_app import celery
from worker.config import get_settings
from worker.tasks.base import get_db_session, get_redis, publish_status, update_task


@celery.task(
    bind=True,
    name="worker.tasks.schema_task.run_schema_induction",
    time_limit=3600,
    soft_time_limit=3600,
)
def run_schema_induction(
    self,
    rag_id: int,
    cycle_id: int,
    task_id: int,
):
    """
    graphrag_lib.run_schema_induction(work_dir, llm_api_url, llm_model) → extracted_ontology.ttl.
    При ошибке — update_task(failed), publish_status(failed), raise.
    """
    settings = get_settings()
    work_dir = Path(settings.work_dir) / f"rag_{rag_id}" / f"cycle_{cycle_id}"
    graphrag_test_dir = Path(settings.graphrag_test_dir)
    r = get_redis()
    db = get_db_session()

    try:
        publish_status(r, task_id, "running", "schema_induction", None)

        if str(graphrag_test_dir) not in sys.path:
            sys.path.insert(0, str(graphrag_test_dir))
        from graphrag_lib import run_schema_induction as _run_schema_induction

        _run_schema_induction(work_dir, settings.llm_api_url, settings.llm_model)

        publish_status(r, task_id, "done", "schema_induction", None)
    except Exception as e:
        err_msg = str(e)
        update_task(db, task_id, "failed", err_msg)
        publish_status(r, task_id, "failed", "schema_induction", err_msg)
        db.close()
        raise
    finally:
        db.close()
