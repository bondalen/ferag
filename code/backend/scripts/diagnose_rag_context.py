#!/usr/bin/env python3
"""
Диагностика RAG: какой контекст попадает в LLM для заданного вопроса.

Помогает понять, почему модель отвечает «нет информации»: если в выводе
скрипта нужного факта нет — проблема в извлечении контекста (граф/ключевые слова);
если факт есть — проблема в модели или промпте.

Запуск из корня репозитория:
  cd code/backend && PYTHONPATH=. python scripts/diagnose_rag_context.py --rag-id 26 --question "В каком году был основан ACME?"

Или с указанием Fuseki (если .env не подгружается):
  cd code/backend && PYTHONPATH=. python scripts/diagnose_rag_context.py --rag-id 26 --question "Кто такой Bob Johnson?" --fuseki-url http://10.7.0.3:3030 --fuseki-user admin --fuseki-password ferag2026
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _load_env() -> None:
    """Подгрузить .env из code/backend при наличии python-dotenv."""
    try:
        from dotenv import load_dotenv
        backend_dir = Path(__file__).resolve().parent.parent
        load_dotenv(backend_dir / ".env")
    except ImportError:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Печать контекста, который RAG передаёт в LLM для данного вопроса (диагностика retrieval)."
    )
    parser.add_argument("--rag-id", type=int, required=True, help="ID RAG (датасет ferag-00001, ...)")
    parser.add_argument("--question", type=str, required=True, help="Вопрос (как в чате)")
    parser.add_argument("--fuseki-url", type=str, default=None, help="Fuseki URL (по умолчанию из .env)")
    parser.add_argument("--fuseki-user", type=str, default=None)
    parser.add_argument("--fuseki-password", type=str, default=None)
    args = parser.parse_args()

    _load_env()

    # Настройки: app (если доступен) или os.environ
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
        from rag_context import build_context_by_question
    except ImportError as e:
        print("Ошибка: rag_context не найден. Запуск: PYTHONPATH=code/backend python3 ...", file=sys.stderr)
        raise SystemExit(1) from e

    sparql_kw = {
        "url": url,
        "auth": (user, password),
        "ds": ds,
    }

    print(f"Вопрос: {args.question!r}")
    print(f"Датасет: {ds}")
    print(f"Fuseki: {url}")
    print("-" * 60)

    context = build_context_by_question(args.question, **sparql_kw)
    print(f"Длина контекста: {len(context)} символов")
    print("-" * 60)
    print(context)
    print("-" * 60)
    print("Если нужного факта нет выше — причина в retrieval (граф или ключевые слова). Если есть — смотреть модель/промпт.")


if __name__ == "__main__":
    main()
