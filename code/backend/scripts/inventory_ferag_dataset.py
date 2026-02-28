#!/usr/bin/env python3
"""
Инвентаризация сущностей и связей в prod-датасете Fuseki для заданного RAG (план 26-0227-1338, шаг 1.1).

SPARQL-запросы: список всех сущностей ferag# (тип, описание), список всех связей (from, to, описание).
Помогает зафиксировать baseline: что есть в графе, чего не хватает (Bob Johnson, GraphRAG, технологии и т.д.).

Запуск:
  cd code/backend && PYTHONPATH=. python scripts/inventory_ferag_dataset.py --rag-id 26
  cd code/backend && PYTHONPATH=. python scripts/inventory_ferag_dataset.py --rag-id 26 --fuseki-url http://10.7.0.3:3030 --fuseki-user admin --fuseki-password ferag2026
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Лимит для «всех» сущностей/связей в одном запросе
INVENTORY_LIMIT = 500


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
        backend_dir = Path(__file__).resolve().parent.parent
        load_dotenv(backend_dir / ".env")
    except ImportError:
        pass


def _local_name(uri: str) -> str:
    return uri.split("#")[-1].split("/")[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Инвентаризация сущностей и связей в prod-датасете Fuseki (ferag-00001, ...)."
    )
    parser.add_argument("--rag-id", type=int, default=26, help="ID RAG (датасет ferag-00026 при 26)")
    parser.add_argument("--fuseki-url", type=str, default=None)
    parser.add_argument("--fuseki-user", type=str, default=None)
    parser.add_argument("--fuseki-password", type=str, default=None)
    args = parser.parse_args()

    _load_env()

    url = args.fuseki_url or os.environ.get("FUSEKI_URL")
    user = args.fuseki_user or os.environ.get("FUSEKI_USER")
    password = args.fuseki_password or os.environ.get("FUSEKI_PASSWORD")
    if not url or not user or not password:
        try:
            from app.config import get_settings
            settings = get_settings()
            url = url or settings.fuseki_url
            user = user or settings.fuseki_user
            password = password or settings.fuseki_password
        except ImportError:
            pass
    if not url or not user or not password:
        print("Укажите FUSEKI_URL, FUSEKI_USER, FUSEKI_PASSWORD в .env или через --fuseki-*", file=sys.stderr)
        raise SystemExit(1)

    ds = f"ferag-{args.rag_id:05d}"

    try:
        from rag_context import sparql, ENTITIES_QUERY, RELATIONSHIPS_QUERY
    except ImportError as e:
        print("Ошибка: rag_context не найден. Запуск: cd code/backend && PYTHONPATH=. python ...", file=sys.stderr)
        raise SystemExit(1) from e

    sparql_kw = {"url": url, "auth": (user, password), "ds": ds}

    print(f"Датасет: {ds}")
    print(f"Fuseki: {url}")
    print("-" * 60)

    # Сущности
    q_entities = ENTITIES_QUERY % INVENTORY_LIMIT
    try:
        j_ent = sparql(q_entities, **sparql_kw)
    except Exception as e:
        print(f"Ошибка запроса сущностей: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    bindings_ent = j_ent.get("results", {}).get("bindings", [])
    entities = []
    for b in bindings_ent:
        name = _local_name(b["s"]["value"])
        type_local = _local_name(b["type"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        entities.append({"name": name, "type": type_local, "description": desc_str})

    print(f"Сущности (всего {len(entities)}):")
    print()
    for e in entities:
        desc_preview = (e["description"][:80] + "…") if len(e["description"]) > 80 else (e["description"] or "—")
        print(f"  {e['name']} (тип: {e['type']})")
        print(f"    описание: {desc_preview}")
        print()
    print("-" * 60)

    # Связи
    q_rels = RELATIONSHIPS_QUERY % INVENTORY_LIMIT
    try:
        j_rel = sparql(q_rels, **sparql_kw)
    except Exception as e:
        print(f"Ошибка запроса связей: {e}", file=sys.stderr)
        raise SystemExit(1) from e

    bindings_rel = j_rel.get("results", {}).get("bindings", [])
    relationships = []
    for b in bindings_rel:
        from_name = _local_name(b["from"]["value"])
        to_name = _local_name(b["to"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        relationships.append({"from_name": from_name, "to_name": to_name, "description": desc_str})

    print(f"Связи (всего {len(relationships)}):")
    print()
    for r in relationships:
        desc_preview = (r["description"][:80] + "…") if len(r["description"]) > 80 else (r["description"] or "—")
        print(f"  {r['from_name']} → {r['to_name']}")
        print(f"    описание: {desc_preview}")
        print()
    print("-" * 60)

    # Сводка: наличие ключевых сущностей/фактов (план 1.1)
    names_lower = {e["name"].lower() for e in entities}
    descs_joined = " ".join(e["description"].lower() for e in entities) + " " + " ".join(r["description"].lower() for r in relationships)
    checklist = {
        "Bob Johnson": "bob" in names_lower or "johnson" in names_lower or "bob johnson" in descs_joined or "bob_johnson" in names_lower,
        "Alice Smith": "alice" in names_lower or "smith" in names_lower or "alice smith" in descs_joined or "alice_smith" in names_lower,
        "GraphRAG": "graphrag" in descs_joined or "graphrag" in names_lower,
        "Fuseki": "fuseki" in descs_joined or "fuseki" in names_lower,
        "PostgreSQL": "postgresql" in descs_joined or "postgresql" in names_lower or "postgres" in descs_joined,
        "AGE": " age " in " " + descs_joined + " " or "age" in names_lower,
        "даты/годы": any(c.isdigit() for c in descs_joined),
        "роли/технологии": len(entities) > 0 and any(len(e["description"]) > 20 for e in entities),
    }
    print("Наличие ключевых сущностей/фактов (baseline):")
    for label, present in checklist.items():
        print(f"  {label}: {'есть' if present else 'нет'}")
    print()
    print(f"Итого: сущностей {len(entities)}, связей {len(relationships)}.")


if __name__ == "__main__":
    main()
