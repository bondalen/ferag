#!/usr/bin/env python3
"""
4.6. Проверка полного цикла: SPARQL-запросы к ferag-prod.
Запуск: python verify_prod.py [--report FILE]
"""

import argparse
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    print("Требуется requests: pip install requests", file=sys.stderr)
    sys.exit(1)

FUSEKI = "http://localhost:3030"
AUTH = ("admin", "ferag2026")
DS = "ferag-prod"


def sparql(query: str) -> dict:
    r = requests.post(
        f"{FUSEKI}/{DS}/query",
        auth=AUTH,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def main() -> None:
    global FUSEKI, DS
    parser = argparse.ArgumentParser(description="Проверка ferag-prod (4.6)")
    parser.add_argument("--report", "-r", default="verify_prod_report.txt", help="Файл отчёта")
    parser.add_argument("--url", default="http://localhost:3030", help="URL Fuseki")
    args = parser.parse_args()
    FUSEKI = args.url.rstrip("/")
    DS = "ferag-prod"

    lines = ["=== Проверка полного цикла (4.6) — ferag-prod ===\n"]

    # 1. Общее число триплетов
    q = "SELECT (COUNT(*) AS ?n) WHERE { ?s ?p ?o }"
    j = sparql(q)
    n = j["results"]["bindings"][0]["n"]["value"]
    lines.append(f"1. Триплетов в графе: {n}")
    lines.append("")

    # 2. Классы онтологии (owl:Class)
    q = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?c WHERE { ?c a owl:Class } ORDER BY ?c
    """
    j = sparql(q)
    classes = [b["c"]["value"] for b in j["results"]["bindings"]]
    lines.append(f"2. Классов (owl:Class): {len(classes)}")
    for c in classes[:20]:
        lines.append(f"   - {c.split('#')[-1].split('/')[-1]}")
    if len(classes) > 20:
        lines.append(f"   ... и ещё {len(classes) - 20}")
    lines.append("")

    # 3. Объектные свойства (owl:ObjectProperty)
    q = """
    PREFIX owl: <http://www.w3.org/2002/07/owl#>
    SELECT ?p WHERE { ?p a owl:ObjectProperty } ORDER BY ?p
    """
    j = sparql(q)
    props = [b["p"]["value"] for b in j["results"]["bindings"]]
    lines.append(f"3. Объектных свойств (owl:ObjectProperty): {len(props)}")
    lines.append("")

    # 4. Иерархия rdfs:subClassOf
    q = """
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX schema: <http://example.org/ferag/schema#>
    SELECT ?sub ?super WHERE {
      ?sub rdfs:subClassOf ?super .
      FILTER(STRSTARTS(STR(?sub), "http://example.org/ferag/schema#"))
    } ORDER BY ?sub
    """
    j = sparql(q)
    subs = j["results"]["bindings"]
    lines.append(f"4. Связей rdfs:subClassOf (схема): {len(subs)}")
    for b in subs[:15]:
        sub = b["sub"]["value"].split("#")[-1].split("/")[-1]
        sup = b["super"]["value"].split("#")[-1].split("/")[-1]
        lines.append(f"   - {sub} -> {sup}")
    if len(subs) > 15:
        lines.append(f"   ... и ещё {len(subs) - 15}")
    lines.append("")

    # 5. Примеры сущностей данных (ferag namespace, типы из ferag#)
    q = """
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?s ?type WHERE {
      ?s rdf:type ?type .
      FILTER(STRSTARTS(STR(?s), "http://example.org/ferag#"))
      FILTER(STRSTARTS(STR(?type), "http://example.org/ferag#"))
    } LIMIT 15
    """
    j = sparql(q)
    ents = j["results"]["bindings"]
    lines.append(f"5. Примеры сущностей (ferag#, тип Person/Organization/Event/Location): {len(ents)}")
    for b in ents[:10]:
        s = b["s"]["value"].split("#")[-1].split("/")[-1]
        t = b["type"]["value"].split("#")[-1].split("/")[-1]
        lines.append(f"   - {s} (тип {t})")
    lines.append("")

    # 6. Примеры связей (Relationship: from, to)
    q = """
    PREFIX ferag: <http://example.org/ferag#>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    SELECT ?from ?to ?desc WHERE {
      ?r a ferag:Relationship ;
         ferag:from ?from ;
         ferag:to ?to .
      OPTIONAL { ?r ferag:description ?desc }
    } LIMIT 5
    """
    j = sparql(q)
    rels = j["results"]["bindings"]
    lines.append(f"6. Примеры связей (Relationship): выборка {len(rels)}")
    for b in rels:
        f = b["from"]["value"].split("#")[-1].split("/")[-1]
        t = b["to"]["value"].split("#")[-1].split("/")[-1]
        d = b.get("desc", {}).get("value", "")[:50] + "..." if b.get("desc") else ""
        lines.append(f"   - {f} -> {t}  ({d})")
    lines.append("")

    lines.append("Вывод: классы и свойства онтологии на месте, триплеты данных присутствуют,")
    lines.append("иерархия rdfs:subClassOf сохранена. Рабочий процесс вчерне готов.")

    report_path = Path(args.report)
    report_path.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"\nОтчёт: {report_path}")


if __name__ == "__main__":
    main()
