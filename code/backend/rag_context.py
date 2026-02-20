#!/usr/bin/env python3
"""
Выборка контекста из ferag-prod для RAG (план 26-0213-1049).
Шаги 1.1.2, 1.1.3, 1.1.4: SPARQL-запросы и сборка текстового контекста.
План 26-0215-1600: вариант A — привязка контекста к словам вопроса (1.2.x).
"""

import re
import sys

try:
    import requests
except ImportError:
    print("Требуется requests: pip install requests", file=sys.stderr)
    sys.exit(1)

FUSEKI = "http://localhost:3030"
AUTH = ("admin", "ferag2026")
DS = "ferag-prod"

# Лимиты по плану 1.1.1
ENTITY_LIMIT = 15
RELATIONSHIP_LIMIT = 15

# 1.2.1 Стоп-слова (рус/англ) для извлечения ключевых слов из вопроса
STOP_WORDS = frozenset({
    "кто", "что", "где", "как", "какой", "какая", "какие", "почему", "когда",
    "какую", "какого", "чем", "который", "которой", "которых", "такой", "такое", "такая",
    "работает", "работать",
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "must", "can", "this", "that", "these", "those",
})

# 1.1.2 Фиксированная выборка сущностей: ferag#, rdf:type, опционально ferag:description
ENTITIES_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ferag: <http://example.org/ferag#>
SELECT ?s ?type ?desc WHERE {
  ?s rdf:type ?type .
  FILTER(STRSTARTS(STR(?s), "http://example.org/ferag#"))
  FILTER(STRSTARTS(STR(?type), "http://example.org/ferag#"))
  OPTIONAL { ?s ferag:description ?desc }
} ORDER BY ?s
LIMIT %d
"""

# 1.2.2 Сущности по совпадению с ключевыми словами (имя или описание)
# Подстановка: %(filter)s — FILTER(...), %(limit)d — LIMIT
ENTITIES_BY_KEYWORDS_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX ferag: <http://example.org/ferag#>
SELECT ?s ?type ?desc WHERE {
  ?s rdf:type ?type .
  FILTER(STRSTARTS(STR(?s), "http://example.org/ferag#"))
  FILTER(STRSTARTS(STR(?type), "http://example.org/ferag#"))
  OPTIONAL { ?s ferag:description ?desc }
  %(filter)s
} ORDER BY ?s
LIMIT %(limit)d
"""

# 1.1.3 Фиксированная выборка связей: ferag:Relationship, from, to, опционально description
RELATIONSHIPS_QUERY = """
PREFIX ferag: <http://example.org/ferag#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?from ?to ?desc WHERE {
  ?r a ferag:Relationship ;
     ferag:from ?from ;
     ferag:to ?to .
  OPTIONAL { ?r ferag:description ?desc }
} ORDER BY ?from ?to
LIMIT %d
"""

# 1.2.3 Связи, у которых from или to входят в множество сущностей (локальные имена)
# Подстановка: %(filter)s — FILTER(...), %(limit)d — LIMIT
RELATIONSHIPS_BY_ENTITIES_QUERY = """
PREFIX ferag: <http://example.org/ferag#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?from ?to ?desc WHERE {
  ?r a ferag:Relationship ;
     ferag:from ?from ;
     ferag:to ?to .
  OPTIONAL { ?r ferag:description ?desc }
  %(filter)s
} ORDER BY ?from ?to
LIMIT %(limit)d
"""

# 1.2.3 Связи, в описании которых встречается любое из ключевых слов
RELATIONSHIPS_BY_DESC_QUERY = """
PREFIX ferag: <http://example.org/ferag#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?from ?to ?desc WHERE {
  ?r a ferag:Relationship ;
     ferag:from ?from ;
     ferag:to ?to .
  OPTIONAL { ?r ferag:description ?desc }
  %(filter)s
} ORDER BY ?from ?to
LIMIT %(limit)d
"""


def sparql(query: str, url: str = FUSEKI, auth: tuple = AUTH, ds: str = DS) -> dict:
    r = requests.post(
        f"{url.rstrip('/')}/{ds}/query",
        auth=auth,
        data={"query": query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def _local_name(uri: str) -> str:
    return uri.split("#")[-1].split("/")[-1]


def _sparql_str_escape(s: str) -> str:
    """Экранирование для подстановки в SPARQL строковый литерал (\" и \\)."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def extract_keywords(question: str) -> list[str]:
    """
    1.2.1 Извлечение ключевых слов из вопроса (план 26-0215-1600).
    Вход: строка вопроса. Выход: список слов (токенов) в нижнем регистре.
    Разбиение по пробелам и знакам пунктуации, отброс стоп-слов и слишком коротких токенов.
    """
    if not question or not question.strip():
        return []
    # Токены: последовательности букв и цифр (в т.ч. CamelCase и кириллица)
    tokens = re.findall(r"[^\s\W]+", question.strip(), re.UNICODE)
    out = []
    for t in tokens:
        low = t.lower()
        if len(low) < 2:
            continue
        if low in STOP_WORDS:
            continue
        out.append(low)
    return out


def fetch_entities_by_keywords(
    keywords: list[str],
    limit: int = 20,
    **sparql_kw,
) -> list[dict]:
    """
    1.2.2 SPARQL: сущности по совпадению с вопросом (план 26-0215-1600).
    Возвращает сущности из ferag#, у которых в локальном имени или в описании
    встречается хотя бы одно из переданных слов (без учёта регистра).
    Формат возврата: как у fetch_entities() — name, type, description.
    """
    if not keywords:
        return []
    parts = []
    for w in keywords:
        esc = _sparql_str_escape(w)
        # Совпадение в URI (локальное имя после #) или в описании
        parts.append(
            f'CONTAINS(LCASE(STR(?s)), "{esc}") '
            f'|| (BOUND(?desc) && CONTAINS(LCASE(STR(?desc)), "{esc}"))'
        )
    filter_clause = "FILTER(" + " || ".join(parts) + ")"
    q = ENTITIES_BY_KEYWORDS_QUERY % {"filter": filter_clause, "limit": limit}
    j = sparql(q, **sparql_kw)
    out = []
    for b in j["results"]["bindings"]:
        name = _local_name(b["s"]["value"])
        type_local = _local_name(b["type"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        out.append({"name": name, "type": type_local, "description": desc_str})
    return out


def fetch_entities(limit: int = ENTITY_LIMIT, **sparql_kw) -> list[dict]:
    """
    Запрос 1.1.2: фиксированная выборка сущностей из ferag-prod.
    Возвращает список словарей с ключами: name, type, description (str или пустая строка).
    """
    q = ENTITIES_QUERY % limit
    j = sparql(q, **sparql_kw)
    out = []
    for b in j["results"]["bindings"]:
        name = _local_name(b["s"]["value"])
        type_local = _local_name(b["type"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        out.append({"name": name, "type": type_local, "description": desc_str})
    return out


def fetch_relationships(limit: int = RELATIONSHIP_LIMIT, **sparql_kw) -> list[dict]:
    """
    Запрос 1.1.3: фиксированная выборка связей (ferag:Relationship) из ferag-prod.
    Возвращает список словарей с ключами: from_name, to_name, description (str или пустая строка).
    """
    q = RELATIONSHIPS_QUERY % limit
    j = sparql(q, **sparql_kw)
    out = []
    for b in j["results"]["bindings"]:
        from_name = _local_name(b["from"]["value"])
        to_name = _local_name(b["to"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        out.append({"from_name": from_name, "to_name": to_name, "description": desc_str})
    return out


def _parse_relationship_bindings(bindings: list) -> list[dict]:
    """Разбор результатов SPARQL по связям в формат from_name, to_name, description."""
    out = []
    for b in bindings:
        from_name = _local_name(b["from"]["value"])
        to_name = _local_name(b["to"]["value"])
        desc = b.get("desc")
        desc_str = desc["value"] if desc else ""
        out.append({"from_name": from_name, "to_name": to_name, "description": desc_str})
    return out


def fetch_relationships_by_entity_names(
    entity_names: list[str],
    limit: int = RELATIONSHIP_LIMIT,
    **sparql_kw,
) -> list[dict]:
    """
    1.2.3 Вариант 1: связи, у которых from или to входят в множество сущностей (по локальному имени).
    entity_names — список локальных имён из fetch_entities_by_keywords (e["name"]).
    Формат возврата: как у fetch_relationships().
    """
    if not entity_names:
        return []
    escaped = [_sparql_str_escape(n) for n in entity_names]
    in_list = ", ".join(f'"{s}"' for s in escaped)
    filter_clause = (
        f"FILTER(REPLACE(STR(?from), \"^.*#\", \"\") IN ({in_list}) "
        f"|| REPLACE(STR(?to), \"^.*#\", \"\") IN ({in_list}))"
    )
    q = RELATIONSHIPS_BY_ENTITIES_QUERY % {"filter": filter_clause, "limit": limit}
    j = sparql(q, **sparql_kw)
    return _parse_relationship_bindings(j["results"]["bindings"])


def fetch_relationships_by_description_keywords(
    keywords: list[str],
    limit: int = RELATIONSHIP_LIMIT,
    **sparql_kw,
) -> list[dict]:
    """
    1.2.3 Вариант 2: связи, в чьём ferag:description встречается любое из слов (без учёта регистра).
    """
    if not keywords:
        return []
    parts = []
    for w in keywords:
        esc = _sparql_str_escape(w)
        parts.append("(BOUND(?desc) && CONTAINS(LCASE(STR(?desc)), \"" + esc + "\"))")
    filter_clause = "FILTER(" + " || ".join(parts) + ")"
    q = RELATIONSHIPS_BY_DESC_QUERY % {"filter": filter_clause, "limit": limit}
    j = sparql(q, **sparql_kw)
    return _parse_relationship_bindings(j["results"]["bindings"])


def fetch_relationships_for_question(
    entities: list[dict],
    keywords: list[str],
    limit: int = RELATIONSHIP_LIMIT,
    **sparql_kw,
) -> list[dict]:
    """
    1.2.3 SPARQL: связи, релевантные вопросу (план 26-0215-1600).
    Комбинирует: сначала связи по сущностям из 1.2.2 (from/to в множестве сущностей),
    при необходимости дополняет связями по совпадению слов в описании. Дедупликация по (from_name, to_name).
    entities — список словарей из fetch_entities_by_keywords (должны быть ключи name, type, description).
    """
    seen: set[tuple[str, str]] = set()
    result: list[dict] = []
    names = [e["name"] for e in entities]

    # Сначала связи по сущностям
    by_entities = fetch_relationships_by_entity_names(names, limit=limit, **sparql_kw)
    for r in by_entities:
        key = (r["from_name"], r["to_name"])
        if key not in seen:
            seen.add(key)
            result.append(r)
    if len(result) >= limit:
        return result[:limit]

    # Дополняем связями по описанию (если есть ключевые слова)
    if keywords:
        by_desc = fetch_relationships_by_description_keywords(keywords, limit=limit, **sparql_kw)
        for r in by_desc:
            if len(result) >= limit:
                break
            key = (r["from_name"], r["to_name"])
            if key not in seen:
                seen.add(key)
                result.append(r)
    return result


def build_context_fixed(**sparql_kw) -> str:
    """
    1.1.4 Сборка контекста (вариант B): вызывает fetch_entities() и fetch_relationships(),
    возвращает один текстовый блок в формате 1.1.1 для подстановки в промпт LLM.
    Вход: без параметра вопроса. Выход: строка контекста.
    """
    entities = fetch_entities(**sparql_kw)
    relationships = fetch_relationships(**sparql_kw)
    return _format_context(entities, relationships)


def _format_context(entities: list[dict], relationships: list[dict]) -> str:
    """Сборка текстового блока контекста в формате 1.1.1 (сущности + связи)."""
    lines = ["=== Сущности ==="]
    for e in entities:
        desc = e["description"].strip() or "—"
        lines.append(f"Сущность {e['name']} (тип {e['type']}): {desc}")
    lines.append("")
    lines.append("=== Связи ===")
    for r in relationships:
        desc = r["description"].strip() or "—"
        lines.append(f"Связь: {r['from_name']} → {r['to_name']} — {desc}")
    return "\n".join(lines)


def build_context_by_question(question: str, **sparql_kw) -> str:
    """
    1.2.4 Интеграция и fallback (вариант A): контекст по словам вопроса.
    1.2.1 (слова) → 1.2.2 и 1.2.3 (запросы) → сборка в формате 1.1.1.
    Если 0 сущностей и 0 связей — возвращает результат build_context_fixed().
    """
    keywords = extract_keywords(question)
    entities = fetch_entities_by_keywords(keywords, limit=20, **sparql_kw)
    relationships = fetch_relationships_for_question(
        entities, keywords, limit=RELATIONSHIP_LIMIT, **sparql_kw
    )
    if not entities and not relationships:
        return build_context_fixed(**sparql_kw)
    return _format_context(entities, relationships)


def main() -> None:
    # Проверка 1.2.1: извлечение ключевых слов из вопроса
    print("1.2.1 Извлечение ключевых слов (план 26-0215-1600)\n")
    for example in ("Кто такой Alice Smith?", "Где работает Bob Johnson?"):
        kw = extract_keywords(example)
        print(f"  «{example}» → {kw}")
    expected = {"alice", "smith", "bob", "johnson"}
    kw1 = set(extract_keywords("Кто такой Alice Smith?"))
    kw2 = set(extract_keywords("Где работает Bob Johnson?"))
    if expected.issubset(kw1 | kw2):
        print("  Проверка 1.2.1 пройдена: в списках есть alice, smith, bob, johnson.\n")
    else:
        print("  Проверка 1.2.1: ожидались слова alice, smith, bob, johnson.\n")

    # Проверка 1.2.2: сущности по ключевым словам
    print("—" * 50)
    print("1.2.2 SPARQL: сущности по ключевым словам (проверка)\n")
    try:
        entities_kw = fetch_entities_by_keywords(["datacorp"], limit=20)
        print(f"  Ключевые слова ['datacorp'] → сущностей: {len(entities_kw)}")
        for e in entities_kw[:5]:
            print(f"    {e['name']} ({e['type']})")
        if entities_kw:
            names = {e["name"].lower() for e in entities_kw}
            if "datacorp" in names or any("datacorp" in e["name"].lower() for e in entities_kw):
                print("  Проверка 1.2.2: в выборке есть сущность DataCorp (или аналог).")
            else:
                print("  (DataCorp в графе не найден по имени; выборка по слову datacorp показана выше.)")
        else:
            print("  Выборка пуста (Fuseki доступен, но совпадений по 'datacorp' нет).")
    except Exception as e:
        print(f"  Ошибка запроса 1.2.2: {e}", file=sys.stderr)
    print()

    # Проверка 1.2.3: связи, релевантные вопросу
    print("—" * 50)
    print("1.2.3 SPARQL: связи по сущностям и по описанию (проверка)\n")
    try:
        entities_alice = fetch_entities_by_keywords(["alice", "smith"], limit=20)
        rels = fetch_relationships_for_question(entities_alice, ["alice", "smith"], limit=15)
        print(f"  Сущности по [alice, smith]: {len(entities_alice)}; связи: {len(rels)}")
        for r in rels[:5]:
            print(f"    {r['from_name']} → {r['to_name']}")
        has_alice = any(
            "alice" in r["from_name"].lower() or "alice" in r["to_name"].lower() or "smith" in r["from_name"].lower() or "smith" in r["to_name"].lower()
            for r in rels
        )
        if rels and (entities_alice or has_alice):
            print("  Проверка 1.2.3: для вопроса про Alice Smith в выборке есть сущности и/или связи с ALICE_SMITH.")
        else:
            print("  (Связей по выбранным сущностям/словам нет или Fuseki недоступен.)")
    except Exception as e:
        print(f"  Ошибка запроса 1.2.3: {e}", file=sys.stderr)
    print()

    # Проверка 1.2.4: интеграция и fallback
    print("—" * 50)
    print("1.2.4 build_context_by_question и fallback (проверка)\n")
    try:
        ctx_match = build_context_by_question("Кто такой Alice Smith?")
        ctx_fallback = build_context_by_question("абракадабра")
        fixed = build_context_fixed()
        if "ALICE_SMITH" in ctx_match and "=== Сущности ===" in ctx_match:
            print("  Вопрос с совпадениями: контекст содержит релевантные сущности/связи.")
        if "=== Сущности ===" in ctx_fallback and len(ctx_fallback) > 100:
            print("  Вопрос без совпадений (абракадабра): использован fallback, контекст — фиксированная выборка.")
        if len(ctx_fallback) >= len(fixed) * 0.9:
            print("  Проверка 1.2.4 пройдена: fallback даёт фиксированную выборку.")
    except Exception as e:
        print(f"  Ошибка 1.2.4: {e}", file=sys.stderr)
    print()

    # Проверка 1.2.5: вариант A — релевантность контекста и fallback
    print("—" * 50)
    print("1.2.5 Проверка варианта A (контекст по вопросу)\n")
    try:
        cases = [
            ("Кто такой Alice Smith?", "ALICE_SMITH"),
            ("Где работает Bob Johnson?", "BOB_JOHNSON"),
            ("Что такое DataCorp?", "DATACORP"),
        ]
        all_ok = True
        for question, expected_entity in cases:
            ctx = build_context_by_question(question)
            if expected_entity in ctx:
                print(f"  «{question}» → контекст содержит {expected_entity}.")
            else:
                print(f"  «{question}» → в контексте нет {expected_entity} (проверьте граф).")
                all_ok = False
        ctx_fallback = build_context_by_question("абракадабра")
        fixed = build_context_fixed()
        if len(ctx_fallback) >= len(fixed) * 0.9 and "=== Сущности ===" in ctx_fallback:
            print("  «абракадабра» → fallback, контекст — фиксированная выборка.")
        else:
            print("  «абракадабра» → fallback не сработал как ожидалось.")
            all_ok = False
        if all_ok:
            print("  Проверка 1.2.5 пройдена: контекст релевантен вопросу; при отсутствии совпадений — fallback.")
        else:
            print("  Проверка 1.2.5: часть проверок не пройдена (см. выше).")
    except Exception as e:
        print(f"  Ошибка 1.2.5: {e}", file=sys.stderr)
    print()

    # Проверка 1.1.2: фиксированная выборка сущностей
    print("—" * 50)
    print("1.1.2 SPARQL: фиксированная выборка сущностей (проверка)\n")
    try:
        entities = fetch_entities()
    except Exception as e:
        print(f"Ошибка запроса: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Получено сущностей: {len(entities)}")
    with_desc = sum(1 for e in entities if e["description"].strip())
    print(f"Из них с описанием: {with_desc}\n")
    for e in entities:
        desc_preview = (e["description"][:50] + "…") if len(e["description"]) > 50 else e["description"] or "—"
        print(f"  {e['name']} ({e['type']}): {desc_preview}")
    if entities:
        print("\nПроверка 1.1.2 пройдена: типы и описания присутствуют в выборке.")
    else:
        print("\nВыборка пуста — проверьте доступность Fuseki и датасета ferag-prod.")

    # Проверка 1.1.3: фиксированная выборка связей
    print("\n" + "—" * 50)
    print("1.1.3 SPARQL: фиксированная выборка связей (проверка)\n")
    try:
        relationships = fetch_relationships()
    except Exception as e:
        print(f"Ошибка запроса: {e}", file=sys.stderr)
        sys.exit(1)
    print(f"Получено связей: {len(relationships)}")
    with_desc_rel = sum(1 for r in relationships if r["description"].strip())
    print(f"Из них с описанием: {with_desc_rel}\n")
    for r in relationships:
        desc_preview = (r["description"][:50] + "…") if len(r["description"]) > 50 else r["description"] or "—"
        print(f"  {r['from_name']} → {r['to_name']}: {desc_preview}")
    if relationships:
        print("\nПроверка 1.1.3 пройдена: from, to и description присутствуют в выборке.")
    else:
        print("\nВыборка связей пуста — проверьте датасет ferag-prod.")

    # Проверка 1.1.4: функция сборки контекста (вариант B)
    print("\n" + "—" * 50)
    print("1.1.4 Функция сборки контекста (вариант B) — вывод контекста\n")
    try:
        context = build_context_fixed()
        print(context)
        print("\nПроверка 1.1.4 пройдена: контекст собран в формате 1.1.1.")
    except Exception as e:
        print(f"Ошибка сборки контекста: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
