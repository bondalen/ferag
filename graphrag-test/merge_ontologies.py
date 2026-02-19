#!/usr/bin/env python3
"""
4.3. Слияние онтологий (задачи 6.13, 6.16).

Сравнивает две онтологии (цикл 1 и цикл 2), формирует результирующую
интегрированную онтологию: объединение классов и свойств, сохранение
иерархии rdfs:subClassOf, объединение domain/range для объектных свойств.

Использование:
  python merge_ontologies.py [--ontology1 FILE] [--ontology2 FILE] [--output FILE]
  По умолчанию: ontology1 = extracted_ontology_full.ttl, ontology2 = ../graphrag-test-cycle2/extracted_ontology_cycle2.ttl,
  output = integrated_ontology.ttl
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    from rdflib import Graph, Namespace
    from rdflib.namespace import OWL, RDF, RDFS
except ImportError:
    print("Требуется rdflib: pip install rdflib", file=sys.stderr)
    sys.exit(1)

SCHEMA = Namespace("http://example.org/ferag/schema#")


def _local_name(uri):
    return uri.split("#")[-1].split("/")[-1] if hasattr(uri, "split") else str(uri).split("#")[-1].split("/")[-1]


def merge_ontologies(
    path1: Path,
    path2: Path,
    out_path: Path,
    report_path: Optional[Path] = None,
) -> Path:
    """
    Сливает две онтологии (TTL) в одну. Записывает результат в out_path.
    Если report_path задан — пишет текстовый отчёт. Возвращает out_path.
    """
    path1, path2, out_path = Path(path1), Path(path2), Path(out_path)
    for p in (path1, path2):
        if not p.exists():
            raise FileNotFoundError(f"Не найден файл: {p}")

    g1 = Graph()
    g2 = Graph()
    g1.parse(path1, format="turtle")
    g2.parse(path2, format="turtle")

    merged = Graph()
    for t in g1:
        merged.add(t)
    for t in g2:
        merged.add(t)

    classes1 = {s for s in g1.subjects(RDF.type, OWL.Class)}
    classes2 = {s for s in g2.subjects(RDF.type, OWL.Class)}
    props1 = {s for s in g1.subjects(RDF.type, OWL.ObjectProperty)}
    props2 = {s for s in g2.subjects(RDF.type, OWL.ObjectProperty)}
    classes1_n = {_local_name(s) for s in classes1}
    classes2_n = {_local_name(s) for s in classes2}
    props1_n = {_local_name(s) for s in props1}
    props2_n = {_local_name(s) for s in props2}

    only1_classes = classes1_n - classes2_n
    only2_classes = classes2_n - classes1_n
    common_classes = classes1_n & classes2_n
    only1_props = props1_n - props2_n
    only2_props = props2_n - props1_n
    common_props = props1_n & props2_n

    report_lines = [
        "=== Отчёт слияния онтологий (4.3) ===",
        f"Онтология 1: {path1}",
        f"Онтология 2: {path2}",
        f"Результат:   {out_path}",
        "",
        "Классы только в цикле 1: " + (", ".join(sorted(only1_classes)) if only1_classes else "нет"),
        "Классы только в цикле 2: " + (", ".join(sorted(only2_classes)) if only2_classes else "нет"),
        "Классы в обоих: " + str(len(common_classes)),
        "",
        "Свойства только в цикле 1: " + (", ".join(sorted(only1_props)) if only1_props else "нет"),
        "Свойства только в цикле 2: " + (", ".join(sorted(only2_props)) if only2_props else "нет"),
        "Свойства в обоих: " + str(len(common_props)),
        "",
        f"Триплетов в онтологии 1: {len(g1)}",
        f"Триплетов в онтологии 2: {len(g2)}",
        f"Триплетов в результирующей: {len(merged)}",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(out_path), format="turtle", encoding="utf-8")
    if report_path is not None:
        Path(report_path).write_text("\n".join(report_lines), encoding="utf-8")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Слияние онтологий цикл 1 + цикл 2")
    parser.add_argument("--ontology1", "-1", default="extracted_ontology_full.ttl", help="Онтология цикла 1 (TTL)")
    parser.add_argument("--ontology2", "-2", default="../graphrag-test-cycle2/extracted_ontology_cycle2.ttl", help="Онтология цикла 2 (TTL)")
    parser.add_argument("--output", "-o", default="integrated_ontology.ttl", help="Выходной TTL")
    parser.add_argument("--report", "-r", default="merge_ontology_report.txt", help="Текстовый отчёт сравнения")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    path1 = (root / args.ontology1) if not Path(args.ontology1).is_absolute() else Path(args.ontology1)
    path2 = (root / args.ontology2) if not Path(args.ontology2).is_absolute() else Path(args.ontology2)
    out_path = (root / args.output) if not Path(args.output).is_absolute() else Path(args.output)
    report_path = (root / args.report) if not Path(args.report).is_absolute() else Path(args.report)

    try:
        merge_ontologies(path1, path2, out_path, report_path)
        print(f"Записано: {out_path}")
        print(f"Отчёт:    {report_path}")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
