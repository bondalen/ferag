"""Celery-задача: GraphRAG index и конвертация в RDF (graphrag_output.ttl)."""
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

from worker.celery_app import celery
from worker.config import get_settings
from worker.tasks.base import get_db_session, get_redis, publish_status, update_task


def _prepare_work_dir(work_dir: Path, input_file: str) -> None:
    """Создаёт work_dir/input, копирует input_file в input/source.txt (если не то же самое)."""
    work_dir = Path(work_dir)
    input_dir = work_dir / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    dest = input_dir / "source.txt"
    src = Path(input_file)
    if src.resolve() != dest.resolve():
        shutil.copy2(input_file, dest)


def _write_settings_yaml(work_dir: Path, settings_content: str, llm_api_url: str, llm_model: str) -> None:
    """Пишет settings.yaml в work_dir, подменяя api_base и model для completion model."""
    try:
        data = yaml.safe_load(settings_content)
    except Exception:
        out = settings_content.replace("http://10.7.0.3:1234/v1", llm_api_url)
        out = out.replace("llama-3.3-70b-instruct", llm_model)
        (work_dir / "settings.yaml").write_text(out, encoding="utf-8")
        return
    # graphrag 3.x: completion_models.default_completion_model
    if data and "completion_models" in data and "default_completion_model" in data["completion_models"]:
        data["completion_models"]["default_completion_model"]["api_base"] = llm_api_url
        data["completion_models"]["default_completion_model"]["model"] = llm_model
    # graphrag 2.x / legacy: models.default_chat_model
    elif data and "models" in data and "default_chat_model" in data["models"]:
        data["models"]["default_chat_model"]["api_base"] = llm_api_url
        data["models"]["default_chat_model"]["model"] = llm_model
    (work_dir / "settings.yaml").write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


@celery.task(
    bind=True,
    name="worker.tasks.graphrag_task.run_graphrag",
    time_limit=3600,
    soft_time_limit=3600,
)
def run_graphrag(
    self,
    rag_id: int,
    cycle_id: int,
    task_id: int,
    input_file: str,
):
    """
    1. Подготовить work_dir/input/source.txt
    2. Создать settings.yaml (шаблон из graphrag-test, с подменой api_base/model)
    3. graphrag index --root work_dir
    4. graphrag_lib.run_graphrag_pipeline(work_dir) → graphrag_output.ttl
    5. publish_status (при ошибке — update_task failed, publish_status, raise)
    """
    settings = get_settings()
    work_dir = Path(settings.work_dir) / f"rag_{rag_id}" / f"cycle_{cycle_id}"
    graphrag_test_dir = Path(settings.graphrag_test_dir)
    r = get_redis()
    db = get_db_session()

    try:
        publish_status(r, task_id, "running", "graphrag", None)

        work_dir.mkdir(parents=True, exist_ok=True)
        _prepare_work_dir(work_dir, input_file)

        template_settings = (graphrag_test_dir / "settings.yaml").read_text(encoding="utf-8")
        _write_settings_yaml(work_dir, template_settings, settings.llm_api_url, settings.llm_model)

        prompts_src = graphrag_test_dir / "prompts"
        prompts_dst = work_dir / "prompts"
        if prompts_src.exists() and not prompts_dst.exists():
            shutil.copytree(prompts_src, prompts_dst)

        subprocess.run(
            ["graphrag", "index", "--root", str(work_dir), "--skip-validation"],
            check=True,
            cwd=str(work_dir),
            timeout=3600,
            env={**__import__("os").environ, "PYTHONPATH": ":".join(sys.path)},
        )

        if str(graphrag_test_dir) not in sys.path:
            sys.path.insert(0, str(graphrag_test_dir))
        from graphrag_lib import run_graphrag_pipeline

        run_graphrag_pipeline(work_dir)

        publish_status(r, task_id, "done", "graphrag", None)
    except Exception as e:
        err_msg = str(e)
        update_task(db, task_id, "failed", err_msg)
        publish_status(r, task_id, "failed", "graphrag", err_msg)
        db.close()
        raise
    finally:
        db.close()


