# Итоговая архитектура развёртывания ferag (согласовано)

**Дата согласования:** 2026-02-15  
**Статус:** Зафиксировано, реализация не начата.

---

## Архитектура

### cr-ubu (облачный сервер cloud.ru)

**Характеристики:**
- Ubuntu 22.04, 2 vCPU (10%), 4 GB RAM
- Публичный IP: 176.108.244.252
- WireGuard IP: 10.7.0.1
- Домен: ontoline.ru (SSL уже настроен)

| Компонент | Тип       | Порт                    | Назначение                    |
|-----------|-----------|-------------------------|-------------------------------|
| **Nginx** | Система ✅| 80, 443                 | Reverse proxy, SSL, Vue SPA   |
| **ferag** | Docker ×1 | 127.0.0.1:**47821**     | FastAPI (через Nginx)         |
|           |           | 10.7.0.1:**47379**      | Redis (для Celery на nb-win)  |

**Один контейнер** `ferag` запускает FastAPI и Redis через `supervisord`.  
**Файл:** `deploy/cr-ubu/docker-compose.yml`

---

### nb-win (локальная машина)

**Характеристики:**
- Ryzen 7 8845HS, 64 GB RAM, Windows + WSL2 Ubuntu 24.04
- WireGuard IP: 10.7.0.3

| Компонент    | Тип      | Порт                       | Назначение                        |
|--------------|----------|----------------------------|-----------------------------------|
| **postgres** | Docker   | 10.7.0.3:**45432**         | ferag_app + ferag_projections     |
| **fuseki**   | Docker   | 127.0.0.1:**43030**        | RDF/SPARQL (источник истины)      |
| **worker**   | Docker   | —                          | Celery (GraphRAG + RAG)           |
| **LM Studio**| Windows  | localhost:**41234**        | Llama 3.3 70B Q4_K_M             |

**Три контейнера** (`postgres`, `fuseki`, `worker`). LM Studio — нативно на Windows.  
**Файл:** `deploy/nb-win/docker-compose.yml`

---

## Сетевая топология

```
Интернет (HTTPS 443)
    ↓
ontoline.ru → cr-ubu (Nginx, система)
    ├── /ferag/        → /var/www/ferag/ (Vue SPA, static)
    ├── /ferag/api/    → 127.0.0.1:47821 (FastAPI, Docker)
    └── /ferag/ws/     → 127.0.0.1:47821/ws/ (WebSocket, Docker)

cr-ubu ferag-контейнер:
    ├── FastAPI (порт 47821)
    └── Redis   (порт 47379) ←──── WireGuard ────→ Celery worker (nb-win)

nb-win (WireGuard 10.7.0.3):
    ├── postgres:45432 ← backend (из cr-ubu через WireGuard)
    ├── fuseki:43030   ← worker (внутри Docker-сети nb-win)
    └── LM Studio:41234 ← worker (host.docker.internal)
```

---

## Файлы развёртывания

```
deploy/
├── README.md                        ← Этот обзор (краткий)
├── DEPLOYMENT_SUMMARY.md            ← Полный архитектурный документ
├── PROPOSAL_ferag_under_path.md     ← Детали: Dockerfile, supervisord.conf, и др.
│
├── cr-ubu/
│   ├── docker-compose.yml           # 1 контейнер
│   ├── .env.example                 # Шаблон переменных
│   └── nginx-location-ferag.conf    # Location блоки для системного Nginx
│
└── nb-win/
    ├── docker-compose.yml           # 3 контейнера
    ├── .env.example                 # Шаблон переменных
    └── init-db.sh                   # Инициализация БД (auto)
```

---

## Требования к окружению backend для эндпоинта upload

Эндпоинт `POST /rags/{id}/upload` сохраняет файл в каталог `work_dir` и вызывает цепочку задач Celery (`start_update_chain` из пакета `worker.tasks`). Необходимо:

1. **Импорт worker:** при запуске backend пакет `worker` должен быть доступен для импорта (чтобы вызвать `start_update_chain`). При локальном запуске из `code/backend/` в `PYTHONPATH` должен быть каталог `code/` (родитель и backend, и worker), например: `PYTHONPATH=/path/to/ferag/code uv run uvicorn app.main:app ...`. В коде роутера при необходимости в `sys.path` добавляется `code/` для резервного варианта.

2. **Общий work_dir:** каталог `work_dir` (по умолчанию `/tmp/ferag`) у backend и worker должен указывать на одно и то же место. Backend пишет туда загруженный файл (`rag_{id}/cycle_{cycle_id}/input/source.txt`), worker читает его при выполнении цепочки. При развёртывании в Docker: смонтировать один и тот же volume в контейнеры backend и worker с одним и тем же путём (например, `WORK_DIR=/app/ferag_work` и volume `ferag_work:/app/ferag_work` у обоих сервисов).

Подробнее: [docs/project/PROJECT-004.md](../docs/project/PROJECT-004.md) (раздел 8.1).

---

## Доступ к cr-ubu по SSH

Для автоматизированного деплоя и запуска команд на cr-ubu (в т.ч. из Cursor Agent с nb-win) используется пользователь **cursor-agent** и ключ из репозитория.

| Параметр | Значение |
|----------|----------|
| Хост | `176.108.244.252` (использовать IP; имя `cr-ubu` в среде может не резолвиться) |
| Пользователь | `cursor-agent` |
| Ключ | `проект/.ssh/cursor_agent_key` |
| known_hosts | `проект/.ssh/known_hosts` |

**Пример (из корня репозитория):**
```bash
ssh -i .ssh/cursor_agent_key -o UserKnownHostsFile=.ssh/known_hosts cursor-agent@176.108.244.252 "docker ps"
```

Правило для агента: [.cursor/rules/deploy-cr-ubu-ssh.mdc](../.cursor/rules/deploy-cr-ubu-ssh.mdc). У пользователя cursor-agent нет sudo без пароля; установка в домашний каталог (например Docker Compose v2) — без sudo.

---

## Команды развёртывания

### cr-ubu
```bash
cd /opt/ferag/deploy/cr-ubu
cp .env.example .env && nano .env
sudo cp nginx-location-ferag.conf /etc/nginx/snippets/ferag.conf
# Добавить в /etc/nginx/sites-available/ontoline.ru: include snippets/ferag.conf;
sudo nginx -t && sudo systemctl reload nginx
docker-compose up -d
```

### nb-win
```bash
cd ~/projects/ferag/deploy/nb-win
cp .env.example .env && nano .env
docker-compose up -d
```

---

## Порядок запуска приложения

Чтобы пользователь мог работать с ferag через браузер, компоненты нужно поднимать в порядке зависимостей (кто от кого принимает соединения).

### Предварительные условия (один раз)

| Условие | Где | Проверка |
|--------|-----|----------|
| Туннель WireGuard поднят | nb-win ↔ cr-ubu | `ping 10.7.0.1` с nb-win, `ping 10.7.0.3` с cr-ubu |
| Nginx запущен, конфиг ferag подключён | cr-ubu | `systemctl status nginx`, в vhost есть `include snippets/ferag.conf` |
| Собранный frontend разложен | cr-ubu | файлы в `/var/www/ferag/` (index.html, assets/ и т.д.) |

### Последовательность запуска

**1. nb-win — инфраструктура (PostgreSQL и Fuseki)**

Backend на cr-ubu подключается к PostgreSQL на nb-win. Worker подключается к Fuseki и PostgreSQL. Эти сервисы не зависят от cr-ubu, их нужно поднять первыми.

```bash
# WSL2 или терминал на nb-win
cd ~/projects/ferag/deploy/nb-win
docker-compose up -d postgres fuseki
```

Дождаться готовности: например `docker-compose logs postgres` — сообщение о готовности принять подключения. При первом запуске сработает `init-db.sh`.

**2. cr-ubu — приложение (FastAPI + Redis)**

После того как PostgreSQL доступен по 10.7.0.3:45432, можно запускать контейнер ferag. В нём поднимутся FastAPI (47821) и Redis (47379). Backend при старте проверит подключение к БД.

```bash
# На cr-ubu (SSH или консоль)
cd /opt/ferag/deploy/cr-ubu
docker-compose up -d
```

Проверка: `curl -s http://127.0.0.1:47821/ferag/api/health` (или аналог из вашего API).

**3. nb-win — Celery worker**

Worker подключается к Redis на cr-ubu (10.7.0.1:47379), к PostgreSQL и Fuseki в Docker-сети nb-win. Поэтому worker запускают после того, как на cr-ubu уже работает контейнер ferag (и Redis).

```bash
# nb-win
cd ~/projects/ferag/deploy/nb-win
docker-compose up -d worker
```

Проверка: `docker-compose logs -f worker` — в логах нет ошибок подключения к брокеру/БД/Fuseki.

**4. (Опционально) nb-win — LM Studio**

Нужен только для сценариев с вызовом LLM (RAG-ответы). Без него веб-интерфейс, авторизация, CRUD и постановка задач в очередь работают; задачи, требующие LLM, будут падать или ждать, пока LM Studio не запустят.

- Запустить LM Studio в Windows.
- Загрузить модель, включить сервер (порт 41234 в настройках).
- Проверка из WSL: `curl http://localhost:41234/v1/models`.

### Итоговая схема порядка

```
1. WireGuard + Nginx + /var/www/ferag/  (уже есть / один раз)
2. nb-win:  docker-compose up -d postgres fuseki
3. cr-ubu:  docker-compose up -d
4. nb-win:  docker-compose up -d worker
5. (по необходимости) Windows: LM Studio, сервер на :41234
```

После шагов 1–4 пользователь может открыть `https://ontoline.ru/ferag/`, войти и пользоваться приложением. Функции с LLM заработают после шага 5.

### Ежедневный/перезапуск

- **Вариант A:** на nb-win одной командой поднять всё: `docker-compose up -d` (postgres и fuseki стартуют первыми, worker — после них; если Redis на cr-ubu ещё не поднят, worker будет переподключаться). Затем на cr-ubu: `docker-compose up -d`. Порядок по-прежнему лучше соблюдать: сначала nb-win (postgres, fuseki), потом cr-ubu (ferag), затем при необходимости worker на nb-win (или оставить `docker-compose up -d` на nb-win и просто дождаться готовности Redis).
- **Вариант B (рекомендуемый):**  
  1) nb-win: `docker-compose up -d` (все три контейнера);  
  2) cr-ubu: `docker-compose up -d`.  
  Если worker поднят раньше Redis, он будет ретраить подключение к брокеру — это нормально.

---

## Объединение контейнеров на nb-win и экономия ОЗУ

Вопрос: имеет ли смысл объединить postgres, fuseki и worker в один контейнер, чтобы сэкономить ОЗУ для LLM?

### Что реально съедает память

| Компонент   | Где задаётся объём | Типичный порядок |
|-------------|--------------------|------------------|
| **Fuseki**  | `JVM_ARGS=-Xmx8g` в docker-compose | до 8 ГБ heap |
| **PostgreSQL** | shared_buffers, work_mem (конфиг) | сотни МБ – 1–2 ГБ |
| **Worker**  | число воркеров Celery, размер модели в памяти | сотни МБ |
| **Контейнеры** | накладные расходы Docker на каждый контейнер | десятки МБ на контейнер |

Память приложений (Postgres, JVM Fuseki, процессы worker) **не зависит от того, в одном контейнере они или в разных**. Её задают конфиги и число процессов, а не количество контейнеров.

### Что даёт объединение контейнеров

- **Экономия:** только накладные расходы на лишние контейнеры (namespace, cgroups, docker-proxy при проброске портов) — ориентировочно **десятки мегабайт на контейнер** (суммарно порядка 50–150 МБ при сведении трёх в один).
- **Минусы:** один общий образ и entrypoint/supervisord для postgres + fuseki + worker; сложнее обновлять по отдельности, отлаживать, ограничивать ресурсы по сервисам; при OOM падает весь «комбайн».

**Вывод:** объединение postgres + fuseki + worker в один контейнер **почти не высвобождает ОЗУ** для LLM (выигрыш доли процента от 64 ГБ), при этом заметно усложняет эксплуатацию. Для цели «больше памяти под LLM» это не оправдано.

### Что реально помогает высвободить ОЗУ под LLM

1. **Уменьшить heap Fuseki**  
   Сейчас `-Xmx8g`. Если граф не гигантский, можно поставить, например, `-Xmx4g` или `-Xmx2g` и проверить нагрузку. Экономия — гигабайты.

2. **Ограничить память Postgres**  
   В `postgresql.conf`: уменьшить `shared_buffers` (например до 256MB–512MB), не завышать `work_mem`/`maintenance_work_mem`. Экономия — сотни МБ.

3. **Ограничить воркеры Celery**  
   Меньше параллельных задач — меньше пиковое потребление ОЗУ worker’ом (и меньше конкуренция с LLM при инференсе).

4. **Ограничить память контейнеров**  
   Например, `deploy mem_limit` в docker-compose для postgres/fuseki/worker, чтобы при пиках один сервис не забирал всё и не мешал LLM.

Рекомендация: **не объединять** postgres, fuseki и worker в один контейнер; оставить три контейнера и **настроить лимиты и параметры** (Fuseki -Xmx, Postgres, число воркеров) под доступное ОЗУ и приоритет LLM.

### Если всё же один контейнер на nb-win

Единственный относительно разумный вариант — **объединить только Fuseki и worker** в одном образе (supervisord: java + celery). Postgres в том же контейнере не рекомендуется: отдельный lifecycle, дата-директория, сигналы для корректного shutdown — лишняя сложность и риски. Экономия при «fuseki+worker в одном» — один контейнер (~30–50 МБ накладных), то есть по-прежнему малая доля от объёма, нужного для LLM.

---

## Экзотические порты (нет конфликтов)

| Сервис     | Порт  | Ранее стандартный |
|------------|-------|-------------------|
| FastAPI    | 47821 | 8000 / 8080       |
| Redis      | 47379 | 6379              |
| PostgreSQL | 45432 | 5432              |
| Fuseki     | 43030 | 3030              |
| LM Studio  | 41234 | 1234              |

---

## Что ещё нужно реализовать (не сделано)

- [ ] `code/backend/` — FastAPI приложение (auth, CRUD, WebSocket)
- [ ] `code/backend/Dockerfile` — FastAPI + Redis + supervisord в одном образе
- [ ] `code/worker/` — Celery приложение (GraphRAG + RAG задачи)
- [ ] `code/worker/Dockerfile`
- [ ] `code/frontend/` — Vue приложение
- [ ] Сборка и деплой Vue → `/var/www/ferag/` на cr-ubu
- [ ] Инициализация PostgreSQL расширений (AGE, pgvector) — `nb-win/init-db.sh` дополнить
- [ ] CI/CD (опционально)
