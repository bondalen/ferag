# PROJECT-002: БД, архитектура хранения, GraphRAG и PostgreSQL

Том проектной документации: иерархия знаний, Docker, Fuseki, PostgreSQL, MS GraphRAG, Schema Induction, подходы к онтологиям, RAG и обновление знаний.

---

## 5.3. Иерархия организации знаний (уточнённая)

```
Текст (хаос, максимальная энтропия)
  ↓
Триплеты без онтологии (частичный порядок)
  ↓
RDF/SPARQL + OWL онтология (Apache Jena Fuseki + reasoning)
  ┃
  ┃ ← ВЕРШИНА СЕМАНТИЧЕСКОЙ ОРГАНИЗАЦИИ
  ┃    (Источник истины: формальная семантика, OWL/RDFS inference)
  ┃
  ┗━━━ Ветвление на специализированные представления:
      │
      ├─ Property Graph (PostgreSQL + Apache AGE)
      │  └─ Проекция RDF для быстрых Cypher-запросов
      │
      ├─ Реляционные таблицы (PostgreSQL Materialized Views)
      │  └─ Проекция графа для SQL-агрегации и отчётов
      │
      ├─ JSON документы (PostgreSQL JSONB)
      │  └─ Проекция для API и гибкой схемы
      │
      └─ Векторные индексы (pgvector)
         └─ Проекция для семантического поиска
```

**Ключевой принцип:**
- **Apache Jena Fuseki (RDF/OWL + reasoning)** — источник истины (single source of truth)
- **PostgreSQL + AGE** — рабочий кэш для производительности
- **Materialized Views** — представления для аналитики

---

## 5.4. Docker и базы данных

**Данные Docker:** При движке WSL 2 образы и тома хранятся в виртуальном диске WSL (файл `ext4.vhdx` на диске D:).

**Проверка:** Из терминала Cursor (WSL) команда `docker ps` должна выполняться без ошибок. Если демон недоступен — запустить Docker Desktop в Windows и включить WSL Integration для Ubuntu (Settings → Resources → WSL Integration).

---

**Первый запуск БД (задача 4.4):**

#### PostgreSQL + Apache AGE + pgvector (основная БД)

**Вариант A: VectorGraph (рекомендуется)**

```bash
cd ~/projects
git clone https://github.com/QuixiAI/vectorgraph.git
cd vectorgraph
docker-compose up -d
```

Что включено: PostgreSQL 16 + Apache AGE + pgvector в одном контейнере.  
Подключение: localhost:5432, логин: postgres

**Вариант Б: Apache AGE официальный образ**

```bash
docker run -d --name postgres-age \
  -e POSTGRES_PASSWORD=ferag2026 \
  -p 5432:5432 \
  -v ~/projects/ferag/postgres-data:/var/lib/postgresql/data \
  apache/age:PG16_latest

# Установить pgvector
docker exec -it postgres-age psql -U postgres -c "CREATE EXTENSION vector;"
```

**Настройка после запуска:**

```sql
-- Подключиться: docker exec -it postgres-age psql -U postgres
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Создать граф для знаний
SELECT create_graph('knowledge_graph');
```

---

#### Apache Jena Fuseki (источник истины для онтологии)

**Установка:**

```bash
docker run -d --name fuseki \
  -p 3030:3030 \
  -v ~/projects/ferag/fuseki-data:/fuseki \
  -e ADMIN_PASSWORD=ferag2026 \
  stain/jena-fuseki
```

**Веб-интерфейс:** http://localhost:3030  
**SPARQL endpoint:** http://localhost:3030/$/datasets  
**Поддержка:** RDF, SPARQL 1.1, OWL reasoning, RDFS inference

**Назначение:**
- Хранение онтологии (OWL/RDF-схема) с формальной семантикой
- Хранение всех триплетов (RDF triple store)
- SPARQL-запросы с логическим выводом (inference)
- Источник истины (single source of truth)

**Ключевые возможности:**
- **OWL reasoning:** OWLFBRuleReasoner, OWLMicroReasoner, OWLMiniReasoner
- **RDFS inference:** rdfs:subClassOf, rdfs:subPropertyOf, rdfs:domain, rdfs:range
- **Критично для проекта:** Schema Induction требует inference для иерархии классов, Synthesis требует owl:equivalentClass для объединения онтологий

**Создание dataset:**

```bash
# Через веб-интерфейс: http://localhost:3030 → "Manage datasets" → "New dataset"
# Или через API:
curl -X POST http://localhost:3030/$/datasets \
  -u admin:ferag2026 \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "dbName=ferag&dbType=tdb2"
```

**Загрузка RDF (Turtle формат):**

```bash
curl -X POST http://localhost:3030/ferag/data \
  -u admin:ferag2026 \
  -H "Content-Type: text/turtle" \
  --data-binary @ontology.ttl
```

**SPARQL-запрос с inference:**

```bash
curl -X POST http://localhost:3030/ferag/sparql \
  -H "Accept: application/sparql-results+json" \
  -H "Content-Type: application/sparql-query" \
  --data-binary "SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10"
```

**Пример inference:**

```sparql
# Если в онтологии есть:
:Employee rdfs:subClassOf :Person .
:Alice rdf:type :Employee .

# То Fuseki автоматически выведет:
:Alice rdf:type :Person .  # ← inference!
```

---

**Ресурсы (опционально):** Docker Desktop → Settings → Resources — ограничить Memory/CPUs, чтобы контейнеры не конкурировали с Ollama.

**WSL:** Лимит памяти задаётся в `C:\Users\Admin\.wslconfig` (memory=32GB). После изменений: PowerShell → `wsl --shutdown`.

---

## 6. Организация данных

### 6.1. Разделение дисков (Samsung 990 Pro 2 ТБ)

```
├── C: (Windows 11 Pro, 300 ГБ, NTFS)
│   ├── Windows/
│   ├── Program Files/   (Cursor, Docker Desktop, Ollama, Protégé, QGIS)
│   ├── Users/Admin/AppData/Local/Cursor → D:\AI\Cursor (символическая ссылка)
│   └── [Pagefile.sys]   (16 ГБ)
└── D: (DATA, ~1.7 ТБ, NTFS)
    ├── AI/AI_MODELS/    (Ollama: llama3.2, llama3.3-70b, deepseek-r1)
    ├── AI/WSL/Ubuntu/   (ext4.vhdx)
    ├── AI/Cursor/
    ├── projects/ferag/
    ├── ontologies/
    ├── graphs/
    └── backups/
```

### 6.3. Настройки приложений

**Ollama** (переменная окружения):
```powershell
OLLAMA_MODELS=D:\AI\AI_MODELS
```

**Docker Desktop** (Settings → Resources → Advanced):
```yaml
data-root: D:\AI\WSL\Ubuntu\docker
```

**WSL (.wslconfig)** в `C:\Users\Admin\.wslconfig`:
```ini
[wsl2]
memory=32GB
processors=8
localhostForwarding=true
```

---

## 7. MS GraphRAG и Schema Induction

### 7.1. Почему MS GraphRAG

Community Detection → подсказки для классов онтологии. Hierarchical Communities → иерархия классов (rdfs:subClassOf). Entity Resolution → чистые триплеты. Summarization → контекст для LLM. Недостатки: медленная индексация, нет инкрементальных обновлений. Качество онтологии важнее скорости.

### 7.2. Schema Induction

Автоматическое извлечение OWL/RDF онтологии из триплетов. Инструменты: LlamaIndex SchemaExtractor, кастомные скрипты с Llama 3.3 70B. Вход: триплеты + communities + summaries. Время: 2–4 часа на 10k триплетов. Запускать на ночь или в фоне.

### 7.3. Три подхода к онтологиям

1. **Pydantic-схемы** — быстрый старт, валидация, без inference.  
2. **WebProtégé + Schema Induction** — формальная OWL, визуализация (рекомендуется).  
3. **Fuseki + SPARQL** — inference, формальная семантика (продвинутый).

### 7.4. Рекомендация

Этап 1: PostgreSQL + AGE, Pydantic. Этап 2: Fuseki как источник истины, WebProtégé, Schema Induction. Этап 3: SPARQL inference.

### 7.5. Модель для Schema Induction

Llama 3.3 70B Q4_K_M для извлечения триплетов и Schema Induction; для диалога можно меньшую (7B) для скорости.

---

## 8. PostgreSQL и RAG

### 8.1. PostgreSQL + AGE + pgvector

Open source, без лимитов, multi-model. Альтернатива отклонённому ArangoDB CE.

### 8.2. Архитектура

Источник истины: Fuseki (RDF/OWL). Синхронизация в PostgreSQL: AGE (граф), pgvector (векторы), реляционные таблицы и Materialized Views, JSONB. Единая ACID-транзакция.

### 8.3. RAG для диалога

Вопрос → векторный поиск (pgvector) + граф (AGE Cypher) + при необходимости SQL → контекст → Ollama → ответ. Инструменты: LangChain Hybrid Retriever, LlamaIndex, Ollama.

### 8.4. Обновление знаний

Диалог → новая информация в data/raw → накопление → повтор цикла (GraphRAG → Schema Induction → Синтез). RAG — реал-тайм; индексация — по расписанию (неделя/месяц).

### 8.5. Данные веб-приложения: диалог по RAG (чат)

В контексте веб-приложения (см. [PROJECT-004](PROJECT-004.md)) диалог с моделью по RAG хранится в PostgreSQL (БД приложения ferag_app). Планируемые таблицы: **chat_messages** (id, rag_id, user_id, role, content, context_used, created_at) — каждая реплика пользователя и ассистента; при реализации сжатия длинных диалогов — **chat_session_summary** (или аналог) для хранения резюме старых сообщений. Порядок работы и варианты контекста: [PROJECT-004-chat-dialogue](PROJECT-004-chat-dialogue.md).

---

[← К обзору](PROJECT.md)
