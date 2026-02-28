#!/usr/bin/env python3
"""
Анализ parquet GraphRAG для шага 2.1 плана 26-0227-1338: проверка наличия ключевых фактов
(Bob Johnson, GraphRAG, Fuseki, PostgreSQL, AGE, даты) и сравнение с полями, используемыми в RDF-конвертации.

Запуск: из graphrag-test, с установленными pandas и pyarrow:
  python analyze_parquet_for_rag.py [--root PATH]
  По умолчанию --root . (текущий каталог с output/).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Анализ parquet для RAG: ключевые факты и маппинг в RDF")
    parser.add_argument("--root", type=str, default=".", help="Каталог с output/ (entities, relationships, communities)")
    args = parser.parse_args()
    root = Path(args.root)
    output_dir = root / "output"

    try:
        import pandas as pd
    except ImportError:
        print("Требуется pandas: pip install pandas pyarrow", file=sys.stderr)
        sys.exit(1)

    for name in ["entities.parquet", "relationships.parquet"]:
        p = output_dir / name
        if not p.exists():
            print(f"Файл не найден: {p}", file=sys.stderr)
            sys.exit(1)

    entities = pd.read_parquet(output_dir / "entities.parquet")
    relationships = pd.read_parquet(output_dir / "relationships.parquet")
    communities_path = output_dir / "communities.parquet"
    has_communities = communities_path.exists()
    if has_communities:
        communities = pd.read_parquet(communities_path)
    else:
        communities = None

    # --- 1. Структура и объём ---
    print("=" * 70)
    print("1. СТРУКТУРА PARQUET (GraphRAG output)")
    print("=" * 70)
    print("\nentities.parquet:")
    print(f"  Строк: {len(entities)}, колонки: {list(entities.columns)}")
    print("\nrelationships.parquet:")
    print(f"  Строк: {len(relationships)}, колонки: {list(relationships.columns)}")
    if communities is not None:
        print("\ncommunities.parquet:")
        print(f"  Строк: {len(communities)}, колонки: {list(communities.columns)}")
    else:
        print("\ncommunities.parquet: отсутствует")

    # --- 2. Что попадает в RDF (test_graphrag_to_rdf) ---
    print("\n" + "=" * 70)
    print("2. ИСПОЛЬЗУЕМЫЕ В RDF-КОНВЕРТАЦИИ (test_graphrag_to_rdf.py)")
    print("=" * 70)
    print("  entities:  title, type, description  →  URI, rdf:type, ferag:description")
    print("  relationships: source, target, description, weight  →  from, to, ferag:description, ferag:weight")
    print("  communities: НЕ ИСПОЛЬЗУЮТСЯ в graphrag_to_rdf (только в Schema Induction).")
    print("  Любые другие колонки parquet в RDF не попадают.")

    # --- 3. Поиск ключевых фактов в parquet ---
    keywords = {
        "Bob Johnson": ["bob", "johnson"],
        "GraphRAG": ["graphrag"],
        "Fuseki": ["fuseki"],
        "PostgreSQL": ["postgresql", "postgres"],
        "AGE": ["age"],
        "даты/годы": ["2010", "2015", "2018", "2023", "2024", "january"],
    }

    def search_in_columns(df: pd.DataFrame, columns: list[str]) -> dict[str, bool]:
        found = {}
        for label, terms in keywords.items():
            ok = False
            for col in columns:
                if col not in df.columns:
                    continue
                for _, val in df[col].dropna().items():
                    s = str(val).lower()
                    if any(t in s for t in terms):
                        ok = True
                        break
                if ok:
                    break
            found[label] = ok
        return found

    ent_cols = [c for c in ["title", "type", "description"] if c in entities.columns]
    rel_cols = [c for c in ["source", "target", "description"] if c in relationships.columns]
    found_ent = search_in_columns(entities, ent_cols)
    found_rel = search_in_columns(relationships, rel_cols)

    print("\n" + "=" * 70)
    print("3. НАЛИЧИЕ КЛЮЧЕВЫХ ФАКТОВ В PARQUET")
    print("=" * 70)
    print("\nВ entities (title, type, description):")
    for label, terms in keywords.items():
        print(f"  {label}: {'есть' if found_ent.get(label) else 'нет'}")
    print("\nВ relationships (source, target, description):")
    for label, terms in keywords.items():
        print(f"  {label}: {'есть' if found_rel.get(label) else 'нет'}")

    # --- 4. Примеры сущностей и связей (первые и с ключевыми словами) ---
    print("\n" + "=" * 70)
    print("4. ПРИМЕРЫ СУЩНОСТЕЙ (title, type, description)")
    print("=" * 70)
    for _, row in entities.head(12).iterrows():
        title = row.get("title", "")
        etype = row.get("type", "")
        desc = (str(row.get("description", ""))[:100] + "…") if pd.notna(row.get("description")) and len(str(row.get("description", ""))) > 100 else (row.get("description", "") or "—")
        print(f"  {title} ({etype}): {desc}")

    print("\n" + "=" * 70)
    print("5. ПРИМЕРЫ СВЯЗЕЙ (source → target, description)")
    print("=" * 70)
    for _, row in relationships.head(12).iterrows():
        src = row.get("source", "")
        tgt = row.get("target", "")
        desc = (str(row.get("description", ""))[:80] + "…") if pd.notna(row.get("description")) and len(str(row.get("description", ""))) > 80 else (row.get("description", "") or "—")
        print(f"  {src} → {tgt}: {desc}")

    # --- 6. Типы сущностей и маппинг в RDF ---
    print("\n" + "=" * 70)
    print("6. ТИПЫ СУЩНОСТЕЙ И МАППИНГ В RDF (type_map)")
    print("=" * 70)
    if "type" in entities.columns:
        for t, count in entities["type"].value_counts().items():
            rdf_type = "Person/Organization/Event/Location" if str(t).upper() in ("PERSON", "ORGANIZATION", "EVENT", "GEO") else "Thing (остальные)"
            print(f"  {t}: {count}  →  {rdf_type}")
    print("\nВ test_graphrag_to_rdf: PERSON→Person, ORGANIZATION→Organization, EVENT→Event, GEO→Location; остальные → ferag:Thing.")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
