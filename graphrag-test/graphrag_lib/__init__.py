"""
Обёртки над скриптами graphrag-test для программного вызова из worker.
Экспорт: run_graphrag_pipeline, run_schema_induction, merge_ontologies, merge_triples.
"""
from pathlib import Path
import sys
from typing import Optional

# Обеспечиваем импорт скриптов из родительского каталога (graphrag-test)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from test_graphrag_to_rdf import graphrag_to_rdf as _graphrag_to_rdf
from test_schema_induction import run_schema_induction as _run_schema_induction
from merge_ontologies import merge_ontologies as _merge_ontologies
from merge_triples import merge_triples as _merge_triples


def run_graphrag_pipeline(work_dir: Path) -> Path:
    """
    Конвертация output/ (parquet) в RDF. Возвращает путь к graphrag_output.ttl.
    work_dir — каталог цикла (содержит output/).
    """
    work_dir = Path(work_dir)
    out_path = work_dir / "graphrag_output.ttl"
    return _graphrag_to_rdf(work_dir, out_path)


def run_schema_induction(work_dir: Path, llm_base_url: str, model: str) -> Path:
    """
    Schema Induction: LLM по output/ → онтология. Возвращает путь к extracted_ontology.ttl.
    """
    work_dir = Path(work_dir)
    out_path = work_dir / "extracted_ontology.ttl"
    return _run_schema_induction(work_dir, out_path, llm_base_url=llm_base_url, model=model)


def merge_ontologies(onto1: Path, onto2: Path, out_path: Path, report_path: Optional[Path] = None) -> Path:
    """Слияние двух онтологий (TTL) в одну. Возвращает out_path."""
    return _merge_ontologies(Path(onto1), Path(onto2), Path(out_path), report_path=report_path)


def merge_triples(triples1: Path, triples2: Path, out_path: Path, report_path: Optional[Path] = None) -> Path:
    """Слияние двух файлов триплетов (TTL) в один. Возвращает out_path."""
    return _merge_triples(Path(triples1), Path(triples2), Path(out_path), report_path=report_path)


__all__ = ["run_graphrag_pipeline", "run_schema_induction", "merge_ontologies", "merge_triples"]
