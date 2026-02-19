#!/usr/bin/env python3
"""
4.4. Слияние массивов триплетов (задачи 6.14, 6.15).

Объединяет триплеты из ferag-staging (цикл 1) и ferag-staging-cycle2 (цикл 2):
- Дедупликация: одинаковые (субъект, предикат, объект) учитываются один раз.
- Разрешение коллизий: при одном и том же (s, ferag:description) с разным объектом
  оставляется описание из цикла 2 (более новое). Связи (Relationship) с одинаковыми
  from, to, description объединяются в одну.

Вход: graphrag_output.ttl (цикл 1), graphrag_output_cycle2.ttl (цикл 2).
Выход: integrated_triples.ttl, merge_triples_report.txt.
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional

try:
    from rdflib import BNode, Graph, URIRef
    from rdflib.namespace import RDF
except ImportError:
    print("Требуется rdflib: pip install rdflib", file=sys.stderr)
    sys.exit(1)

FERAG = "http://example.org/ferag#"


def merge_triples(
    path1: Path,
    path2: Path,
    out_path: Path,
    report_path: Optional[Path] = None,
) -> Path:
    """
    Сливает два TTL-файла триплетов в один (дедупликация, коллизии description из g2).
    Записывает результат в out_path. Если report_path задан — пишет отчёт. Возвращает out_path.
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
    for p, n in g1.namespace_manager.namespaces():
        merged.bind(p or "ferag", n)

    desc_uri = URIRef(FERAG + "description")
    from_uri = URIRef(FERAG + "from")
    to_uri = URIRef(FERAG + "to")
    rel_type = URIRef(FERAG + "Relationship")

    for t in g1:
        merged.add(t)

    descriptions_g2 = list(g2.triples((None, desc_uri, None)))
    for s, p, o in descriptions_g2:
        if not isinstance(s, BNode):
            to_remove = list(merged.triples((s, desc_uri, None)))
            for t in to_remove:
                merged.remove(t)
            merged.add((s, p, o))

    added = 0
    skipped_dup = 0
    for s, p, o in g2:
        if (s, p, o) in merged:
            skipped_dup += 1
            continue
        if p == desc_uri and not isinstance(s, BNode):
            continue
        merged.add((s, p, o))
        added += 1

    rel_by_key = defaultdict(list)
    for b in list(merged.subjects(RDF.type, rel_type)):
        if not isinstance(b, BNode):
            continue
        from_val = list(merged.objects(b, from_uri))
        to_val = list(merged.objects(b, to_uri))
        desc_val = list(merged.objects(b, desc_uri))
        if not from_val or not to_val:
            continue
        key = (from_val[0], to_val[0], desc_val[0] if desc_val else None)
        rel_by_key[key].append(b)

    for key, nodes in rel_by_key.items():
        if len(nodes) <= 1:
            continue
        for b in nodes[1:]:
            for (bs, bp, bo) in list(merged.triples((b, None, None))):
                merged.remove((bs, bp, bo))
            for (bs, bp, bo) in list(merged.triples((None, None, b))):
                merged.remove((bs, bp, bo))

    report_lines = [
        "=== Отчёт слияния массивов триплетов (4.4) ===",
        f"Вход 1: {path1}  (триплетов: {len(g1)})",
        f"Вход 2: {path2}  (триплетов: {len(g2)})",
        f"Выход:  {out_path}  (триплетов: {len(merged)})",
        "",
        "Дедупликация: одинаковые (s, p, o) учитываются один раз.",
        "Коллизии (s, ferag:description, o): оставлено описание из цикла 2.",
        "Связи (Relationship) с одинаковыми from, to, description объединены в одну.",
        "",
        f"Добавлено триплетов из цикла 2 (без точных дубликатов): {added}",
        f"Пропущено точных дубликатов при добавлении из g2: {skipped_dup}",
        f"Дубликатов связей по (from, to, description) удалено: {sum(max(0, len(nodes)-1) for nodes in rel_by_key.values())}",
    ]

    out_path.parent.mkdir(parents=True, exist_ok=True)
    merged.serialize(destination=str(out_path), format="turtle", encoding="utf-8")
    if report_path is not None:
        Path(report_path).write_text("\n".join(report_lines), encoding="utf-8")

    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Слияние массивов триплетов (4.4)")
    parser.add_argument("--triples1", "-1", default="graphrag_output.ttl", help="Триплеты цикла 1")
    parser.add_argument("--triples2", "-2", default="../graphrag-test-cycle2/graphrag_output_cycle2.ttl", help="Триплеты цикла 2")
    parser.add_argument("--output", "-o", default="integrated_triples.ttl", help="Выходной TTL")
    parser.add_argument("--report", "-r", default="merge_triples_report.txt", help="Отчёт")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent
    path1 = (root / args.triples1) if not Path(args.triples1).is_absolute() else Path(args.triples1)
    path2 = (root / args.triples2) if not Path(args.triples2).is_absolute() else Path(args.triples2)
    out_path = (root / args.output) if not Path(args.output).is_absolute() else Path(args.output)
    report_path = (root / args.report) if not Path(args.report).is_absolute() else Path(args.report)

    try:
        merge_triples(path1, path2, out_path, report_path)
        print(f"Записано: {out_path}")
        print(f"Отчёт:    {report_path}")
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
