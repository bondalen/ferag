#!/usr/bin/env python3
"""
Сценарий п. 6 Финальная проверка (26-0219-1110).
Требует: backend на BASE_URL (с CELERY_BROKER_URL и CELERY_RESULT_BACKEND в env), Redis, worker, Fuseki, LLM (например на 10.7.0.3:1234).
"""
import json
import os
import sys
import time

import requests

BASE_URL = os.environ.get("FERAG_API", "http://127.0.0.1:47822")
SOURCE_FILE = os.environ.get(
    "FERAG_SOURCE_FILE",
    os.path.join(os.path.dirname(__file__), "..", "graphrag-test", "input", "source.txt"),
)

def main():
    print("1. Health...")
    r = requests.get(f"{BASE_URL}/health", timeout=5)
    r.raise_for_status()
    print("   OK")

    print("2. Register + Login...")
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={"email": "finalcheck@example.com", "password": "test123456"},
        timeout=5,
    )
    if r.status_code not in (200, 409):  # 409 = already registered
        print(f"   Register: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "finalcheck@example.com", "password": "test123456"},
        timeout=5,
    )
    r.raise_for_status()
    token = r.json()["access_token"]
    print("   OK, token received")

    print("3. Create RAG...")
    r = requests.post(
        f"{BASE_URL}/rags",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Final check RAG", "description": None},
        timeout=5,
    )
    r.raise_for_status()
    rag = r.json()
    rag_id = rag["id"]
    print(f"   OK, rag_id={rag_id}")

    print("4. Upload...")
    if not os.path.isfile(SOURCE_FILE):
        print(f"   ERROR: file not found: {SOURCE_FILE}")
        sys.exit(1)
    with open(SOURCE_FILE, "rb") as f:
        r = requests.post(
            f"{BASE_URL}/rags/{rag_id}/upload",
            headers={"Authorization": f"Bearer {token}"},
            files={"file": ("source.txt", f, "text/plain")},
            timeout=30,
        )
    r.raise_for_status()
    data = r.json()
    cycle_id = data["cycle_id"]
    task_id = data["task_id"]
    print(f"   OK, cycle_id={cycle_id}, task_id={task_id}")

    print("5. WebSocket: wait for status 'done' (polling /tasks/{id})...")
    for _ in range(1440):  # 2 hours
        r = requests.get(
            f"{BASE_URL}/tasks/{task_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        r.raise_for_status()
        t = r.json()
        status = t.get("status")
        print(f"   status={status}")
        if status == "done":
            break
        if status == "failed":
            print(f"   ERROR: task failed: {t.get('error', '')}")
            sys.exit(1)
        time.sleep(5)
    else:
        print("   ERROR: timeout waiting for done")
        sys.exit(1)
    print("   OK")

    print("6. Approve cycle...")
    r = requests.post(
        f"{BASE_URL}/rags/{rag_id}/cycles/{cycle_id}/approve",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    print("   OK")

    print("7. GET /rags/{id} -> cycle_count...")
    r = requests.get(
        f"{BASE_URL}/rags/{rag_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5,
    )
    r.raise_for_status()
    rag2 = r.json()
    assert rag2.get("cycle_count") == 1, f"cycle_count={rag2.get('cycle_count')}"
    print(f"   OK, cycle_count={rag2['cycle_count']}")

    print("8. POST /rags/{id}/chat...")
    r = requests.post(
        f"{BASE_URL}/rags/{rag_id}/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": "Кто такая Alice Smith?"},
        timeout=120,
    )
    r.raise_for_status()
    chat = r.json()
    answer = chat.get("answer", "")
    if not answer or len(answer) < 10:
        print(f"   WARNING: short or empty answer: {answer!r}")
    else:
        print(f"   OK, answer length={len(answer)}")
        print(f"   Answer (first 300 chars): {answer[:300]}...")

    print("\n=== Финальная проверка пройдена ===")


if __name__ == "__main__":
    main()
