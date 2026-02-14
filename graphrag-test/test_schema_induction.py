#!/usr/bin/env python3
"""
3.3. Schema Induction: полная OWL-онтология из триплетов, сущностей и сообществ GraphRAG.

Читает output/entities.parquet, relationships.parquet, communities.parquet, community_reports.parquet,
формирует полный промпт для LLM, вызывает LM Studio (Llama 3.3 70B), сохраняет результат в Turtle.

Требует: LM Studio запущен, модель загружена, Local Server (Serve on Local Network).
Context Length в LM Studio: если уменьшен — поставьте не меньше 8192 (лучше 16384). По умолчанию 128K достаточно.
Запуск может занять 15–30 минут (полный промпт, до 8192 токенов ответа).

Запуск: python test_schema_induction.py [--output FILE]
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd
from openai import OpenAI

LM_STUDIO_BASE = "http://10.7.0.3:1234/v1"
MODEL = "llama-3.3-70b-instruct"
OUTPUT_DEFAULT = "extracted_ontology.ttl"
MAX_RESPONSE_TOKENS = 8192
TIMING_FILE = "schema_induction_timing.json"
# Полная онтология может генерироваться 20–40 мин — увеличиваем таймаут HTTP
REQUEST_TIMEOUT_SEC = 3600


def load_data(root: Path):
    root = Path(root)
    entities = pd.read_parquet(root / "output" / "entities.parquet")
    rels = pd.read_parquet(root / "output" / "relationships.parquet")
    comms = pd.read_parquet(root / "output" / "communities.parquet")
    reports = pd.read_parquet(root / "output" / "community_reports.parquet")
    return entities, rels, comms, reports


def build_prompt(
    entities: pd.DataFrame,
    rels: pd.DataFrame,
    comms: pd.DataFrame,
    reports: pd.DataFrame,
) -> str:
    lines = []

    # Типы сущностей из данных — чтобы онтология была полной
    if "type" in entities.columns:
        type_counts = entities["type"].value_counts()
        lines.append("ENTITY TYPES (from data, include each as owl:Class):")
        for etype, count in type_counts.items():
            lines.append(f"  - {etype}: {count} entities")
        lines.append("")

    lines.append("TRIPLETS (subject, object, relationship description) — include each relationship type as owl:ObjectProperty:")
    for _, row in rels.iterrows():
        s, t, d = row["source"], row["target"], row.get("description", "")
        d = (d or "").strip()
        lines.append(f"  - {s} -> {t}: {d}")

    lines.append("\nCOMMUNITIES (title, level, full summary):")
    for _, row in reports.iterrows():
        title = row.get("title", "")
        level = row.get("level", "")
        summary = (row.get("summary") or "").strip()
        lines.append(f"  - [{level}] {title}: {summary}")

    prompt_instruction = """
From the data above, extract a COMPLETE OWL ontology in Turtle format. You MUST:
1. Define an owl:Class for every entity type listed (and any extra from communities).
2. Define an owl:ObjectProperty for every distinct relationship type that appears in the triplets.
3. Add rdfs:subClassOf hierarchy where appropriate (e.g. Company subClassOf Organization).
4. For every object property, add rdfs:domain and rdfs:range to the classes you defined.

Use prefix: @prefix : <http://example.org/ferag/schema#> .
Output ONLY valid Turtle, no markdown or explanation before/after. If you use a code block, use ```turtle and ```.
"""
    return "\n".join(lines) + "\n" + prompt_instruction


def extract_turtle(text: str) -> str:
    """Извлекает блок Turtle из ответа (убирает markdown, лишний текст)."""
    text = text.strip()
    # Блок ```turtle ... ```
    m = re.search(r"```(?:turtle|ttl)?\s*\n(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    # Иначе считаем весь ответ Turtle (модель могла выдать только RDF)
    return text


def main() -> None:
    parser = argparse.ArgumentParser(description="Schema Induction: full ontology from triplets + entities + communities")
    parser.add_argument("--output", "-o", default=OUTPUT_DEFAULT, help="Output .ttl file")
    parser.add_argument("--root", default=".", help="Project root (with output/)")
    args = parser.parse_args()

    root = Path(args.root)
    for name in ["entities.parquet", "relationships.parquet", "communities.parquet", "community_reports.parquet"]:
        if not (root / "output" / name).exists():
            print(f"Ошибка: не найден output/{name}", file=sys.stderr)
            sys.exit(1)

    entities, rels, comms, reports = load_data(root)
    prompt = build_prompt(entities, rels, comms, reports)
    prompt_chars = len(prompt)

    print("Полная онтология: все триплеты и отчёты сообществ. Вызов LM Studio (может занять 15–40 мин)...")
    t0 = time.perf_counter()
    client = OpenAI(base_url=LM_STUDIO_BASE, api_key="lm-studio", timeout=REQUEST_TIMEOUT_SEC)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=MAX_RESPONSE_TOKENS,
        temperature=0.0,
    )
    t1 = time.perf_counter()
    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        print("Пустой ответ от модели.", file=sys.stderr)
        sys.exit(1)

    turtle = extract_turtle(raw)
    out_path = root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(turtle, encoding="utf-8")
    print(f"Записано: {out_path} ({len(turtle)} символов)")

    if out_path.suffix.lower() == ".ttl":
        owl_path = out_path.with_suffix(".owl")
        owl_path.write_text(turtle, encoding="utf-8")
        print(f"Копия: {owl_path}")

    # Замер времени и объёмов — для фиксации затрат по объёму текста
    usage = getattr(resp, "usage", None)
    total_tokens = None
    if usage is not None:
        total_tokens = getattr(usage, "total_tokens", None) or (
            (getattr(usage, "prompt_tokens", 0) or 0) + (getattr(usage, "completion_tokens", 0) or 0)
        )
    timing = {
        "wall_clock_seconds": round(t1 - t0, 2),
        "entities_count": len(entities),
        "triplets_count": len(rels),
        "communities_count": len(reports),
        "prompt_chars": prompt_chars,
        "output_chars": len(turtle),
        "output_tokens": total_tokens,
    }
    timing_path = root / TIMING_FILE
    timing_path.write_text(json.dumps(timing, indent=2), encoding="utf-8")
    print(f"Время и объёмы: {timing_path} ({timing['wall_clock_seconds']} с)")


if __name__ == "__main__":
    main()
