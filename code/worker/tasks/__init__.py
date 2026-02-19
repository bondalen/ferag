# Celery tasks: graphrag, schema_induction, merge, staging, chain
from celery import chain

from worker.tasks.base import on_chain_failure
from worker.tasks.graphrag_task import run_graphrag
from worker.tasks.merge_task import do_merge
from worker.tasks.schema_task import run_schema_induction
from worker.tasks.staging_task import load_to_staging


def start_update_chain(rag_id: int, cycle_id: int, task_id: int, input_file: str):
    """
    Запуск цепочки: run_graphrag → run_schema_induction → do_merge → load_to_staging.
    Возвращает AsyncResult. При падении любого шага вызывается on_chain_failure (Task.status='failed', publish).
    """
    return chain(
        run_graphrag.s(rag_id, cycle_id, task_id, input_file),
        run_schema_induction.si(rag_id, cycle_id, task_id),
        do_merge.si(rag_id, cycle_id, task_id),
        load_to_staging.si(rag_id, cycle_id, task_id),
    ).apply_async(link_error=on_chain_failure.s())
