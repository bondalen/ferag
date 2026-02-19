"""Celery-задача: merge_ontologies + merge_triples → integrated_*.ttl."""
import sys
from pathlib import Path

from worker.celery_app import celery
from worker.config import get_settings
from worker.fuseki_client import export_dataset_to_ttl, rag_prod_dataset
from worker.tasks.base import get_db_session, get_redis, publish_status, update_task


@celery.task(
    bind=True,
    name="worker.tasks.merge_task.do_merge",
    time_limit=3600,
    soft_time_limit=3600,
)
def do_merge(
    self,
    rag_id: int,
    cycle_id: int,
    task_id: int,
):
    """
    Скачать prod-данные из Fuseki, merge_ontologies(extracted, prod) → integrated_ontology.ttl,
    merge_triples(graphrag_output, prod) → integrated_triples.ttl.
    При ошибке — update_task(failed), publish_status(failed), raise.
    """
    settings = get_settings()
    work_dir = Path(settings.work_dir) / f"rag_{rag_id}" / f"cycle_{cycle_id}"
    graphrag_test_dir = Path(settings.graphrag_test_dir)
    r = get_redis()
    db = get_db_session()

    try:
        publish_status(r, task_id, "running", "merge", None)

        prod_ds = rag_prod_dataset(rag_id)
        prod_export = work_dir / "prod_export.ttl"
        export_dataset_to_ttl(prod_ds, prod_export)

        if str(graphrag_test_dir) not in sys.path:
            sys.path.insert(0, str(graphrag_test_dir))
        from graphrag_lib import merge_ontologies, merge_triples

        extracted = work_dir / "extracted_ontology.ttl"
        graphrag_output = work_dir / "graphrag_output.ttl"
        merge_ontologies(extracted, prod_export, work_dir / "integrated_ontology.ttl")
        merge_triples(graphrag_output, prod_export, work_dir / "integrated_triples.ttl")

        publish_status(r, task_id, "done", "merge", None)
    except Exception as e:
        err_msg = str(e)
        update_task(db, task_id, "failed", err_msg)
        publish_status(r, task_id, "failed", "merge", err_msg)
        db.close()
        raise
    finally:
        db.close()
