# PROJECT-004: Веб-приложение и развёртывание

Том проектной документации: архитектура веб-приложения ferag, двухмашинная топология, технологический стек, компоненты, маршрутизация, ключевые архитектурные решения.

**Статус:** архитектура согласована (2026-02-15), реализация не начата.  
**Задачи:** Блок 9 в [TASKS.md](../tasks/TASKS.md).  
**Операционные файлы:** [deploy/](../../deploy/) (docker-compose, .env.example, nginx config).

---

## 1. Цель и контекст

RAG-диалог по графу достигнут в рамках лабораторных скриптов (план 26-0215-1600). Следующий этап — веб-приложение, позволяющее нескольким пользователям:

- регистрироваться и аутентифицироваться;
- создавать и редактировать свои графовые RAG;
- загружать тексты для построения графа (асинхронно, в фоне);
- задавать вопросы по RAG в диалоговом интерфейсе;
- приглашать других пользователей к совместной работе со своим RAG.

Ожидаемая нагрузка: единицы–десятки пользователей одновременно.

---

## 2. Двухмашинная топология

Приложение развёртывается на двух машинах, связанных туннелем WireGuard.

### cr-ubu (облачный сервер cloud.ru)

| Параметр | Значение |
|----------|----------|
| ОС | Ubuntu 22.04 |
| Ресурсы | 2 vCPU (10% гарантированных), 4 GB RAM |
| Публичный IP | 176.108.244.252 |
| WireGuard IP | 10.7.0.1 |
| Домен | ontoline.ru (SSL уже настроен) |

**Компоненты:**

| Компонент | Тип | Порт | Назначение |
|-----------|-----|------|------------|
| **Nginx** | Система | 80, 443 | Reverse proxy, SSL termination, раздача Vue SPA |
| **ferag** | Docker ×1 | 127.0.0.1:47821 | FastAPI — auth, CRUD, WebSocket |
| | | 10.7.0.1:47379 | Redis — очередь задач Celery |

Один контейнер `ferag` запускает FastAPI и Redis через **supervisord**. Nginx установлен в системе (не в Docker): обслуживает уже существующий сайт ontoline.ru, к нему добавляются location-блоки для ferag.

### nb-win (локальная машина)

| Параметр | Значение |
|----------|----------|
| Железо | GMKtec NucBox K8 Plus, Ryzen 7 8845HS, 64 GB RAM |
| ОС | Windows 11 + WSL2 Ubuntu 24.04 |
| WireGuard IP | 10.7.0.3 |

**Компоненты:**

| Компонент | Тип | Порт | Назначение |
|-----------|-----|------|------------|
| **postgres** | Docker | 10.7.0.3:45432 | ferag_app (данные приложения) + ferag_projections (AGE, pgvector) |
| **fuseki** | Docker | localhost:43030 | Apache Jena Fuseki — RDF/SPARQL, источник истины |
| **worker** | Docker | — | Celery worker — задачи GraphRAG, RAG, индексации |
| **LM Studio** | Windows | localhost:41234 | Llama 3.3 70B Q4_K_M — инференс LLM |

Три контейнера управляются одним `docker-compose.yml`. LM Studio запускается нативно в Windows.

### Сетевая топология

```
Интернет (HTTPS 443)
    ↓
ontoline.ru → cr-ubu (Nginx, система)
    ├── /ferag/        → /var/www/ferag/       (Vue SPA, static)
    ├── /ferag/api/    → 127.0.0.1:47821       (FastAPI, Docker)
    └── /ferag/ws/     → 127.0.0.1:47821/ws/   (WebSocket, Docker)

cr-ubu ferag-контейнер:
    ├── FastAPI (47821)
    └── Redis   (47379) ←──── WireGuard ────→ Celery worker (nb-win)

nb-win (10.7.0.3 по WireGuard):
    ├── postgres:45432  ← FastAPI backend (из cr-ubu)
    ├── fuseki:43030    ← Celery worker (внутри Docker-сети nb-win)
    └── LM Studio:41234 ← Celery worker (через host.docker.internal)
```

---

## 3. URL-схема приложения

Все элементы приложения ferag сгруппированы под префиксом `/ferag/`, чтобы не конфликтовать с остальным содержимым ontoline.ru.

| URL | Назначение |
|-----|------------|
| `https://ontoline.ru/ferag/` | Vue SPA — вход, список RAG, загрузка текстов, диалог |
| `https://ontoline.ru/ferag/api/` | FastAPI REST API — auth, rags, upload, chat, tasks |
| `https://ontoline.ru/ferag/ws/` | WebSocket — статусы задач индексации в реальном времени |

Корень `https://ontoline.ru/` и путь `/files` не затрагиваются.

---

## 4. Технологический стек

| Слой | Технология | Обоснование |
|------|-----------|-------------|
| Frontend | Vue 3 + Vite | SPA, сборка с `base: '/ferag/'` |
| Backend API | FastAPI (Python) | Async, OpenAPI, WebSocket, JWT |
| Очередь задач | Celery + Redis | Асинхронная индексация GraphRAG |
| Брокер | Redis 7 | Встроен в контейнер ferag через supervisord |
| База данных | PostgreSQL 16 | ferag_app (данные), ferag_projections (AGE, pgvector) |
| Граф (источник истины) | Apache Jena Fuseki | RDF/OWL, SPARQL, inference |
| LLM инференс | LM Studio (Windows) | Llama 3.3 70B Q4_K_M, порт 41234 |
| Reverse proxy | Nginx (система, cr-ubu) | SSL, статика, проксирование API/WS |
| VPN | WireGuard | Защищённый канал cr-ubu ↔ nb-win |
| Аутентификация | JWT (FastAPI) | Stateless, токены в заголовках |

---

## 5. Ключевые архитектурные решения

### 5.1 PostgreSQL и Fuseki — на nb-win, а не на cr-ubu

Оба сервиса уже работают на nb-win и являются частью основного рабочего цикла (GraphRAG → Schema Induction → Fuseki). Перенос на cr-ubu потребовал бы:
- дополнительной памяти (cr-ubu имеет 4 GB RAM; Fuseki занимает до 8 GB JVM heap);
- дублирования данных;
- перестройки уже налаженного цикла.

Решение: оставить на nb-win, backend обращается к PostgreSQL через WireGuard (10.7.0.3:45432).

### 5.2 Один контейнер на cr-ubu (FastAPI + Redis через supervisord)

cr-ubu имеет 4 GB RAM. Два отдельных контейнера (FastAPI и Redis) несут незначительные дополнительные накладные расходы (несколько десятков МБ на container runtime), но усложняют управление. Объединение через supervisord:
- экономит RAM (накладные расходы одного контейнера вместо двух);
- даёт один docker-compose.yml с одной секцией `services`;
- Redis и FastAPI общаются на `127.0.0.1` внутри контейнера (нет сетевого хопа).

### 5.3 Экзотические порты (диапазон 43000–47999)

Порты выбраны из диапазона, не зарезервированного IANA и крайне редко используемого:

| Сервис | Порт | Вместо стандартного |
|--------|------|---------------------|
| FastAPI | 47821 | 8000 / 8080 |
| Redis | 47379 | 6379 |
| PostgreSQL | 45432 | 5432 |
| Fuseki | 43030 | 3030 |
| LM Studio | 41234 | 1234 |

Цель: исключить конфликты со службами, которые уже могут быть запущены на портах по умолчанию (в том числе существующий сайт ontoline.ru).

### 5.4 Объединение контейнеров nb-win ради экономии ОЗУ — нецелесообразно

Возможный запрос: объединить postgres, fuseki и worker в один контейнер, чтобы высвободить ОЗУ для LLM.

Вывод: не оправдано. Память определяется конфигурацией приложений, а не числом контейнеров:
- Fuseki: до 8 GB (JVM `-Xmx8g`);
- PostgreSQL: сотни МБ – 1–2 GB (shared_buffers и т.д.);
- Worker: сотни МБ.

Экономия от объединения — только накладные расходы Docker (~50–150 МБ суммарно), тогда как LLM (Llama 3.3 70B Q4_K_M) требует ~40–45 GB.

**Что реально помогает:** уменьшить Fuseki heap (`-Xmx4g` или `-Xmx2g`, если граф не гигантский), поджать `shared_buffers` PostgreSQL, ограничить число воркеров Celery, задать `mem_limit` контейнерам в docker-compose.

### 5.6 Python вместо Java для backend и worker

При проектировании рассматривалась возможность использования Java-стека (Spring Boot) для backend и worker. Принятое решение — остаться на Python. Обоснование:

**Worker не может быть Java.** Всё ML/AI-ядро — MS GraphRAG, LlamaIndex (Schema Induction), openai-клиент, существующий `graphrag-test/` — Python-only. Перенос на Java невозможен без обёртки через subprocess/REST, что добавляет хрупкость.

**Backend на Java при Python-worker = полиглот без выгод.** Два языка, два build-инструмента, усложнение деплоя — при сохранении всей ML-части на Python. Выгоды Java (зрелая типизация, enterprise-транзакции, высококонкурентные сервисы) избыточны для данного масштаба (единицы–десятки пользователей).

**Ресурсы cr-ubu.** Spring Boot JVM требует ~250–400 МБ только на старт; на cr-ubu с 4 GB RAM это ощутимо. FastAPI + uvicorn занимают ~50 МБ.

**FastAPI не является компромиссом.** Современный фреймворк: строгая типизация (Pydantic v2), нативный async, автодокументация (OpenAPI), производительность уровня Node.js/Go в I/O-сценариях.

Python «вошёл сам собой» — закономерно, поскольку ML/AI-экосистема де-факто является Python-экосистемой.

---

### 5.5 Маршрутизация Nginx

Nginx проксирует `/ferag/api/` → FastAPI (47821), отбрасывая префикс `/ferag/api` при `proxy_pass http://127.0.0.1:47821/`. FastAPI слушает на корне — роуты без дополнительного префикса. Порядок location-блоков: сначала более специфичные (`/ferag/api/`, `/ferag/ws/`), затем общий `/ferag/`.

---

## 6. Маршрутизация Nginx (конфиг)

```nginx
# Добавить в server { listen 443 ssl ... } в /etc/nginx/sites-available/ontoline.ru

# Backend API
location /ferag/api/ {
    proxy_pass http://127.0.0.1:47821/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 300s;
    proxy_send_timeout 300s;
    proxy_read_timeout 300s;
}

# WebSocket
location /ferag/ws/ {
    proxy_pass http://127.0.0.1:47821/ws/;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
}

# Vue SPA (fallback на index.html)
location /ferag/ {
    alias /var/www/ferag/;
    try_files $uri $uri/ /ferag/index.html;
}

location /ferag {
    alias /var/www/ferag;
    index index.html;
    try_files $uri $uri/ /ferag/index.html;
}
```

Готовый файл: [deploy/cr-ubu/nginx-location-ferag.conf](../../deploy/cr-ubu/nginx-location-ferag.conf).

---

## 7. Frontend и Backend: интеграция с путём `/ferag/`

**Vue (Vite):**
- `base: '/ferag/'` в `vite.config.ts` — статика запрашивается как `/ferag/assets/...`.
- API-запросы: на `/ferag/api/` (относительный путь того же хоста).
- WebSocket: `wss://ontoline.ru/ferag/ws/`.
- CORS на backend разрешить для `https://ontoline.ru`.

**FastAPI:**
- Слушает на корне `http://127.0.0.1:47821/`.
- Роуты: `prefix="/auth"` → внешний URL `/ferag/api/auth/...`, `prefix="/rags"` → `/ferag/api/rags`, и т.д.
- Опционально: `root_path="/ferag/api"` для корректного отображения в OpenAPI (`/docs`).

---

## 8. Контейнер ferag на cr-ubu: supervisord

```dockerfile
# code/backend/Dockerfile (эскиз)
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    redis-server supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . /app
WORKDIR /app
COPY supervisord.conf /etc/supervisor/conf.d/ferag.conf

EXPOSE 47821 47379
CMD ["supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
```

```ini
# supervisord.conf (эскиз)
[supervisord]
nodaemon=true

[program:redis]
command=redis-server --port 47379 --appendonly yes --dir /data
autostart=true
autorestart=true

[program:backend]
command=uvicorn main:app --host 0.0.0.0 --port 47821
directory=/app
autostart=true
autorestart=true
```

---

## 9. Порядок запуска

```
1. WireGuard туннель + Nginx + /var/www/ferag/  (один раз)
2. nb-win:  docker-compose up -d postgres fuseki
3. cr-ubu:  docker-compose up -d
4. nb-win:  docker-compose up -d worker
5. (по необходимости) Windows: LM Studio, сервер на :41234
```

После шагов 1–4 пользователь может открыть `https://ontoline.ru/ferag/`. Функции с LLM-ответами заработают после шага 5.

Подробности: [deploy/DEPLOYMENT_SUMMARY.md](../../deploy/DEPLOYMENT_SUMMARY.md).

---

[← К обзору](PROJECT.md)
