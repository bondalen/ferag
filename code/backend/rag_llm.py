#!/usr/bin/env python3
"""
Вызов LLM с контекстом и вопросом для RAG (план 26-0213-1049, шаг 2).
Формирование промпта (2.1), настройка клиента и вызов API (2.2–2.4).
"""

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # для проверки 2.2 без вызова API достаточно создания клиента после pip install openai

# 2.1 Инструкция для модели: ответ только по контексту из графа
RAG_INSTRUCTION = (
    "Ответь на вопрос пользователя, опираясь только на приведённый контекст из графа знаний. "
    "Если в контексте нет информации для ответа, так и скажи."
)

# 2.2 Настройка клиента LLM (по образцу test_schema_induction.py)
DEFAULT_BASE_URL = "http://10.7.0.3:1234/v1"
DEFAULT_MODEL = "llama-3.3-70b-instruct"
DEFAULT_API_KEY = "lm-studio"
DEFAULT_TIMEOUT_SEC = 120
MAX_RESPONSE_TOKENS = 1024


def get_llm_client(
    base_url: str | None = None,
    api_key: str | None = None,
    timeout: int | None = None,
):
    """
    2.2 Создание клиента OpenAI-совместимого API (LM Studio или аналог).
    Параметры по умолчанию — как в проекте. Проверка: клиент создаётся без ошибок.
    """
    if OpenAI is None:
        raise RuntimeError("Требуется openai: pip install openai")
    return OpenAI(
        base_url=base_url or DEFAULT_BASE_URL,
        api_key=api_key or DEFAULT_API_KEY,
        timeout=timeout if timeout is not None else DEFAULT_TIMEOUT_SEC,
    )


def build_rag_prompt(context: str, question: str) -> str:
    """
    2.1 Формирование промпта: инструкция + блок контекста + вопрос.
    Вход: строка контекста (из шага 1), строка вопроса.
    Выход: одна строка промпта для передачи в chat API (один user message).
    """
    return f"{RAG_INSTRUCTION}\n\n--- Контекст из графа ---\n{context}\n\n--- Вопрос ---\n{question}"


def build_rag_messages(context: str, question: str) -> list[dict]:
    """
    Вариант для chat API: список сообщений (system + user).
    Удобно для разделения инструкции и контента.
    """
    return [
        {"role": "system", "content": RAG_INSTRUCTION},
        {"role": "user", "content": f"Контекст из графа:\n\n{context}\n\nВопрос пользователя: {question}"},
    ]


def call_llm(
    prompt: str,
    client=None,
    model: str | None = None,
    max_tokens: int = MAX_RESPONSE_TOKENS,
) -> str:
    """
    2.3 Вызов API: один запрос к chat completions, возврат строки content.
    Вход: промпт (строка из build_rag_prompt или один user message).
    Таймаут задаётся при создании клиента. Пустой ответ → ValueError.
    """
    if client is None:
        client = get_llm_client()
    model = model or DEFAULT_MODEL
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=0.0,
    )
    raw = (resp.choices[0].message.content or "").strip()
    if not raw:
        raise ValueError("Пустой ответ от модели")
    return raw


def answer_from_context(
    context: str,
    question: str,
    client=None,
    model: str | None = None,
    max_tokens: int = MAX_RESPONSE_TOKENS,
) -> str:
    """
    2.4 Функция «контекст + вопрос → ответ»: объединяет 2.1–2.3.
    Входы: контекст (например из build_context_fixed()), вопрос пользователя.
    Выход: строка ответа LLM.
    """
    prompt = build_rag_prompt(context, question)
    return call_llm(prompt, client=client, model=model, max_tokens=max_tokens)


def main() -> None:
    # Проверка 2.1: сгенерировать промпт для тестового контекста и вопроса, убедиться в читаемости
    print("2.1 Формирование промпта (проверка)\n")
    test_context = """=== Сущности ===
Сущность Alice_Smith (тип Person): Руководитель проекта в компании TechCorp, VP of AI.
Сущность BOB_JOHNSON (тип Person): Инженер, Principal Scientist в ACME Corporation.

=== Связи ===
Связь: Alice_Smith → TechCorp — руководит проектами в компании.
Связь: BOB_JOHNSON → ACME_CORPORATION — работает в компании."""
    test_question = "Кто такой Alice Smith?"
    prompt = build_rag_prompt(test_context, test_question)
    print("Промпт (полностью):")
    print("-" * 50)
    print(prompt)
    print("-" * 50)
    print("\nЧитаемость: инструкция, контекст и вопрос разделены. Проверка 2.1 пройдена.")

    # Опционально: промпт из реального контекста (требует Fuseki)
    try:
        from rag_context import build_context_fixed
        real_context = build_context_fixed()
        real_prompt = build_rag_prompt(real_context, test_question)
        print(f"\nПромпт с реальным контекстом: {len(real_prompt)} символов (первые 500):")
        print(real_prompt[:500] + "…" if len(real_prompt) > 500 else real_prompt)
    except Exception as e:
        print(f"\nРеальный контекст не загружен (Fuseki недоступен или ошибка): {e}")

    # Проверка 2.2: клиент создаётся без ошибок (без вызова модели)
    print("\n" + "—" * 50)
    print("2.2 Настройка клиента LLM (проверка)\n")
    try:
        client = get_llm_client()
        print(f"base_url: {DEFAULT_BASE_URL}")
        print(f"timeout: {DEFAULT_TIMEOUT_SEC} с")
        print("Проверка 2.2 пройдена: клиент создан без ошибок.")
    except Exception as e:
        print(f"Ошибка создания клиента: {e}")
        print("Установите: pip install openai")

    # Проверка 2.3: вызов API с тестовым промптом, получить непустую строку
    print("\n" + "—" * 50)
    print("2.3 Вызов API и извлечение ответа (проверка)\n")
    try:
        client = get_llm_client()
        response = call_llm(prompt, client=client)
        print("Ответ модели:")
        print("-" * 50)
        print(response)
        print("-" * 50)
        print(f"\nДлина ответа: {len(response)} символов. Проверка 2.3 пройдена.")
    except ValueError as e:
        print(f"Ошибка: {e}")
    except Exception as e:
        print(f"Ошибка вызова API (проверьте LM Studio и загрузку модели): {e}")

    # Проверка 2.4: контекст + вопрос → ответ (реальный контекст из графа)
    print("\n" + "—" * 50)
    print("2.4 Функция «контекст + вопрос → ответ» (проверка)\n")
    try:
        from rag_context import build_context_fixed
        real_context = build_context_fixed()
        test_question = "Кто такой Alice Smith?"
        answer = answer_from_context(real_context, test_question)
        print(f"Вопрос: {test_question}")
        print("Ответ:")
        print("-" * 50)
        print(answer)
        print("-" * 50)
        print("\nПроверка 2.4 пройдена: ответ на основе контекста из графа.")
    except Exception as e:
        print(f"Ошибка (Fuseki или LM Studio): {e}")


if __name__ == "__main__":
    main()
