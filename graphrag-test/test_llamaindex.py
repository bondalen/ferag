#!/usr/bin/env python3
"""
3.2. Тест LlamaIndex с LM Studio (OpenAI-совместимый API).

Требует: LM Studio запущен, модель Llama 3.3 70B загружена,
         Local Server включён, Serve on Local Network → http://10.7.0.3:1234

Запуск: из каталога graphrag-test выполнить
        python test_llamaindex.py

Используется клиент openai с base_url (LM Studio). Для Schema Induction
в 3.3 тот же endpoint доступен через LlamaIndex или прямой openai.
"""

from openai import OpenAI

LM_STUDIO_BASE = "http://10.7.0.3:1234/v1"
MODEL = "llama-3.3-70b-instruct"


def main() -> None:
    client = OpenAI(base_url=LM_STUDIO_BASE, api_key="lm-studio")
    print("Запрос к LM Studio:", MODEL)
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": "What is a knowledge graph? Answer in one short paragraph."}],
        max_tokens=256,
        temperature=0.0,
    )
    text = resp.choices[0].message.content if resp.choices else ""
    print(text)


if __name__ == "__main__":
    main()
