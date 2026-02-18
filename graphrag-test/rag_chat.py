#!/usr/bin/env python3
"""
Минимальный RAG/диалог по графу ferag-prod (план 26-0213-1049, шаг 3).
Вопрос (аргумент или интерактивный ввод) → контекст из графа → LLM → ответ в stdout.
"""

import argparse
import sys

# Контекст из графа (шаг 1, вариант A с fallback)
from rag_context import build_context_by_question, build_context_fixed
# Ответ по контексту (шаг 2)
from rag_llm import answer_from_context


def main() -> None:
    parser = argparse.ArgumentParser(
        description="RAG по графу ferag-prod: вопрос → ответ на основе контекста из графа"
    )
    parser.add_argument(
        "question",
        nargs="?",
        default=None,
        help="Вопрос пользователя (если не указан, используется --interactive)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Интерактивный ввод вопроса (если не передан аргументом)",
    )
    parser.add_argument(
        "--fixed",
        action="store_true",
        help="Использовать фиксированную выборку контекста (вариант B) вместо контекста по вопросу (вариант A)",
    )
    args = parser.parse_args()

    question = args.question
    if not question and args.interactive:
        try:
            question = input("Вопрос: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(file=sys.stderr)
            sys.exit(130)
    if not question:
        parser.error("Укажите вопрос аргументом или используйте --interactive")

    # Шаг 1: получить контекст из ferag-prod (вариант A по умолчанию, при --fixed — вариант B)
    try:
        context = build_context_fixed() if args.fixed else build_context_by_question(question)
    except Exception as e:
        print(f"Ошибка: не удалось получить контекст из графа (Fuseki недоступен или ошибка SPARQL).\n{e}", file=sys.stderr)
        sys.exit(1)

    # Шаг 2: вызов LLM — перед этим предупреждение (нужно запустить LM Studio и модель)
    print("Сейчас будет вызван LLM (LM Studio). Убедитесь, что модель запущена и доступна.", file=sys.stderr)
    try:
        answer = answer_from_context(context, question)
        print(answer)
    except ValueError as e:
        print(f"Ошибка LLM: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Ошибка: LM Studio недоступен или ошибка модели.\n{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
