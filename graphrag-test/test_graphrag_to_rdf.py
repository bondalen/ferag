#!/usr/bin/env python3
"""
2.8. Конвертация результатов GraphRAG в RDF (концептуально).

Читает output/entities.parquet и output/relationships.parquet,
строит RDF-граф (rdflib) и сохраняет в graphrag_output.ttl.

Использование:
  python test_graphrag_to_rdf.py [--output FILE]
  По умолчанию: --output graphrag_output.ttl
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


def slug(s: str) -> str:
    """Делает из строки безопасный локальный идентификатор для URI."""
    s = s.strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\-]", "", s)
    return s or "entity"


def graphrag_to_rdf(root_dir: Path, output_path: Path) -> Path:
    """
    Читает output/entities.parquet и output/relationships.parquet из root_dir,
    строит RDF-граф и сохраняет в output_path. Возвращает output_path.
    При ошибке (нет файлов, нет rdflib) бросает исключение.
    """
    root_dir = Path(root_dir)
    output_path = Path(output_path)
    entities_path = root_dir / "output" / "entities.parquet"
    relationships_path = root_dir / "output" / "relationships.parquet"

    for p in (entities_path, relationships_path):
        if not p.exists():
            raise FileNotFoundError(f"Не найден файл: {p}")

    from rdflib import BNode, Graph, Literal, Namespace
    from rdflib.namespace import RDF

    FERAG = Namespace("http://example.org/ferag#")
    type_map = {
        "PERSON": FERAG.Person,
        "ORGANIZATION": FERAG.Organization,
        "EVENT": FERAG.Event,
        "GEO": FERAG.Location,
    }

    g = Graph()
    g.bind("ferag", FERAG)
    g.bind("rdf", RDF)

    entities_df = pd.read_parquet(entities_path)
    rels_df = pd.read_parquet(relationships_path)

    for _, row in entities_df.iterrows():
        title = str(row["title"]).strip()
        if not title:
            continue
        local = slug(title)
        uri = FERAG[local]
        g.add((uri, RDF.type, type_map.get(str(row["type"]).upper(), FERAG.Thing)))
        if pd.notna(row.get("description")) and str(row["description"]).strip():
            g.add((uri, FERAG.description, Literal(str(row["description"]).strip())))

    for _, row in rels_df.iterrows():
        src = str(row["source"]).strip()
        tgt = str(row["target"]).strip()
        if not src or not tgt:
            continue
        from_uri = FERAG[slug(src)]
        to_uri = FERAG[slug(tgt)]
        desc = str(row.get("description", "") or "").strip()
        weight = row.get("weight")
        b = BNode()
        g.add((b, RDF.type, FERAG.Relationship))
        g.add((b, FERAG["from"], from_uri))
        g.add((b, FERAG["to"], to_uri))
        if desc:
            g.add((b, FERAG.description, Literal(desc)))
        if pd.notna(weight):
            g.add((b, FERAG.weight, Literal(float(weight))))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    g.serialize(destination=str(output_path), format="turtle", encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description="GraphRAG parquet → RDF (Turtle)")
    parser.add_argument("--output", "-o", default="graphrag_output.ttl", help="Выходной .ttl файл")
    parser.add_argument("--root", default=".", help="Корень проекта (папка с output/)")
    args = parser.parse_args()

    root = Path(args.root)
    out_path = root / args.output
    try:
        graphrag_to_rdf(root, out_path)
        print(f"Записано: {out_path}")
    except ImportError:
        print("Установите rdflib: pip install rdflib", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
