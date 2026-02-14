# JOURNAL-001: Прогоны GraphRAG, Schema Induction и второй корпус

Том журнала: итоги индексации GraphRAG, результат Schema Induction, шаблон сравнения CPU vs DirectML, замысел второго корпуса (цикл 2).

---

## 1. Итоги индексации GraphRAG

**Источник:** `graphrag-test/INDEXING_SUMMARY.md`  
**Дата:** 11 февраля 2026  
**Версия GraphRAG:** 2.7.1  
**LLM:** Llama 3.3 70B Instruct Q4_K_M (CPU режим, Ollama)  
**Embeddings:** nomic-embed-text:latest

### Время выполнения

**Общее время:** 5 часов 14 минут 21 секунда (18,861 сек)

**Разбивка по этапам:**
1. **extract_graph** (извлечение сущностей и связей из 3 chunks):
   - Chunk 1: ~43 мин 27 сек (cold start)
   - Chunk 2: ~31 мин 54 сек
   - Chunk 3: ~43 мин 54 сек
   - **Итого: ~2 часа (~8,446 сек)**

2. **summarize_descriptions** (87 описаний сущностей/связей):
   - **Время: ~21 минута 31 секунда**

3. **create_community_reports** (отчеты по сообществам):
   - **Уровень 1** (3 отчета): ~1 час 6 мин
   - **Уровень 0** (3 отчета): ~1 час 47 мин
   - **Итого: ~2 часа 53 мин (~10,402 сек)**

4. **generate_text_embeddings** (41 entity + 6 community + 3 text_unit):
   - **Время: ~12 секунд**

### Статистика извлеченных данных

| Тип данных | Количество | Размер файла |
|------------|------------|--------------|
| Документы | 3 | 18 КБ |
| Текстовые единицы | 3 | 22 КБ |
| Сущности | 41 | 16 КБ |
| Связи | 46 | 12 КБ |
| Сообщества | 6 (3×L0 + 3×L1) | 13 КБ |
| Отчеты по сообществам | 6 | 53 КБ |
| Векторные embeddings | 50 | lancedb/ |

**Типы сущностей:** EVENT 19 (46%), ORGANIZATION 14 (34%), GEO 6 (15%), PERSON 2 (5%).

### Топ-3 сообщества по рейтингу

1. **GraphRAG Community** (уровень 0, рейтинг 8.0) — проект GraphRAG, Microsoft, Llama 3.3 70B, LlamaIndex, Ollama, Fuseki, PostgreSQL, AGE, pgvector.
2. **ACME Corporation and GraphRAG System** (уровень 0, рейтинг 7.5) — Alice Smith, Bob Johnson, Knowledge Graph team.
3. **TechCorp and AI Market** (уровень 0, рейтинг 6.5) — enterprise AI, конкуренция с ACME, Seattle, Knowledge Engineering Division.

### Выводы

- Индексация завершена успешно; request_timeout исправлен (1800 сек).
- Узкое место: Llama 3.3 70B в CPU режиме очень медленная; для 100+ документов потребуются недели/месяцы. Рекомендации: меньшая модель для тестов, LM Studio + DirectML (iGPU), облако или Fedora на отдельном SSD.

**Структура output:** entities.parquet, relationships.parquet, communities.parquet, community_reports.parquet, text_units.parquet, documents.parquet, lancedb/, context.json, stats.json.

---

## 2. Schema Induction — полный прогон

**Источник:** `graphrag-test/SCHEMA_INDUCTION_FULL_SUMMARY.md`  
**Дата:** 12.02.2026

### Что сделано

1. Первый запуск завершился **таймаутом HTTP** (~20 мин): клиент `openai` по умолчанию обрывает соединение. Ошибка: `APITimeoutError: Request timed out`.
2. **Исправление:** в `test_schema_induction.py` добавлен `timeout=3600` (1 ч) для клиента OpenAI.
3. Повторный запуск успешно завершён. Результаты:
   - **extracted_ontology_full.ttl** — 2797 символов, 93 строки
   - **extracted_ontology_full.owl** — копия для загрузки в Fuseki
   - **schema_induction_timing.json** — замер времени и объёмов

### Временные затраты (полный объём текста)

| Метрика | Значение |
|--------|----------|
| Время выполнения | **675.78 с** (~11 мин 16 с) |
| Сущностей на входе | 38 |
| Триплетов | 45 |
| Сообществ | 7 |
| Символов промпта | 8891 |
| Символов ответа | 2797 |
| Токенов ответа | 2933 |

### Содержимое полной онтологии

- **Классы:** Organization, Company, Person, Event, GEO, City, Country, University, Project, System, Technology, Team (с иерархией rdfs:subClassOf).
- **Object properties с domain/range:** worksAt, collaboratedWith, leads, joined, foundedIn, operatesIn, contributesTo, uses, initiatedIn, worksAtCompany, earnedPhDFrom, isSpecialistIn, isHeadOf, competesWith, operatesInMarket, developedBy, usesForEntityExtraction, usesForSchemaInduction, usesForVectorEmbeddings и др.

Дальше по плану: загрузить онтологию в Fuseki (dataset `ferag-ontology`) — `extracted_ontology_full.owl` или `.ttl`.

---

## 3. Сравнение производительности: CPU vs DirectML

**Источник:** `graphrag-test/COMPARISON_TEMPLATE.md`  
**Дата тестирования:** 11 февраля 2026  
**Модель:** Llama 3.3 70B Instruct Q4_K_M (~40 ГБ)  
**Тестовые данные:** 3 документа, 3 текстовых единицы

### Конфигурация 1: CPU (Baseline)

- **Система:** AMD Ryzen 7 8845HS, 56 ГБ (WSL2), Ubuntu 24.04 LTS, Ollama, CPU only.
- **Результаты:** Общее время 5 ч 14 мин; extract_graph ~2 ч; summarize_descriptions ~21 мин; community_reports ~2 ч 53 мин; embeddings ~12 сек. Извлечено: 41 сущность, 46 связей, 6 сообществ, 6 отчётов.

### Конфигурация 2: DirectML (iGPU)

- **Система:** Ryzen 7 8845HS, iGPU AMD Radeon 780M (RDNA 3), 64 ГБ, Windows 11 Pro, LM Studio 0.3.37, DirectML.
- **Результаты:** (шаблон для заполнения после теста — общее время, этапы, количество сущностей/связей/сообществ).

### Сравнительный анализ (шаблон)

| Метрика | CPU (Ollama) | DirectML (LM Studio) | Ускорение |
|---------|--------------|----------------------|-----------|
| Общее время | 5 ч 14 мин | ??? | ??? |
| extract_graph (avg chunk) | ~39 мин | ??? | ??? |
| community_report (avg) | ~29 мин | ??? | ??? |

**Ожидаемое ускорение:** 30–50% (по данным сообщества). **Фактическое:** заполнится после теста.

---

## 4. Второй корпус (цикл 2)

**Источник:** `graphrag-test/input-cycle2/README.md`

Тексты на ту же тематику (персоны, организации, проекты, технологии), с намеренными расхождениями для проверки слияния в Фазе 4.

### Ожидаемые операции при слиянии (4.3–4.4)

**Добавление (новые элементы онтологии и триплеты):**
- Сущности: Carol Davis (Person), DataCorp (Organization/Company), FERAG Consortium (Organization), Knowledge Fusion (Project), FERAG Workshop 2026 (Event), Berlin (City), продукт TechGraph AI (Product).
- Связи/свойства: mentors, reportsTo, fundedBy, participatesIn, acquiredBy (или аналоги), роль/тип Data Engineer.
- Классы онтологии (при необходимости): Product, Consortium, Workshop/Event с уточнениями.

**Изменение (модификация существующих элементов):**
- Alice Smith: senior software engineer → VP of AI; продвижение June 2025.
- Bob Johnson: TechCorp → снова ACME (с May 2025), Principal Scientist; Knowledge Engineering division disbanded у TechCorp.
- GraphRAG: concluded/superseded → преемник Knowledge Fusion / открытый проект FERAG; Schema Induction — Ollama → LM Studio.
- ACME: новый офис Berlin; приобретение DataCorp (late 2024).
- TechCorp и ACME: competesWith → партнёрство, FERAG Consortium.

**Удаление / устаревание:**
- GraphRAG pilot как активный проект — concluded December 2025; триплеты о нём как о текущем — пометить устаревшими или удалить.
- Bob Johnson — worksAt TechCorp, leads Knowledge Engineering at TechCorp — неактуальны после April/May 2025; collaboratesWith (Bob–Alice) в контексте «day-to-day design» — ограничен.
- «Schema Induction uses Ollama» → заменить на LM Studio; соответствующие триплеты обновить или удалить.

**Файлы корпуса:** `cycle2_doc1.txt`, `cycle2_doc2.txt`, `cycle2_doc3.txt`.

---

[← К журналу](JOURNAL.md)
