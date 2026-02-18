# Развёртывание ferag на двух машинах

## Итоговая архитектура

### cr-ubu (облако cloud.ru)

| Компонент   | Тип       | Порт                    | Назначение                        |
|-------------|-----------|-------------------------|-----------------------------------|
| **Nginx**   | Система   | 80, 443                 | Reverse proxy, SSL, Vue SPA       |
| **ferag**   | Docker ×1 | 127.0.0.1:47821         | FastAPI + Redis (supervisord)     |

**1 контейнер, 1 файл docker-compose.yml**

### nb-win (локальная машина)

| Компонент   | Тип       | Порт                    | Назначение                        |
|-------------|-----------|-------------------------|-----------------------------------|
| **postgres**| Docker    | 10.7.0.3:45432          | ferag_app + ferag_projections     |
| **fuseki**  | Docker    | 127.0.0.1:43030         | RDF/SPARQL (источник истины)      |
| **worker**  | Docker    | —                       | Celery (GraphRAG + RAG задачи)    |
| **LM Studio**| Windows  | localhost:41234         | Llama 3.3 70B                     |

**3 контейнера, 1 файл docker-compose.yml**

---

## Структура файлов

```
deploy/
├── cr-ubu/
│   ├── docker-compose.yml        # 1 контейнер (FastAPI + Redis через supervisord)
│   ├── .env.example              # Шаблон переменных → скопировать в .env
│   └── nginx-location-ferag.conf # Location блоки для системного Nginx
└── nb-win/
    ├── docker-compose.yml        # 3 контейнера (postgres, fuseki, worker)
    ├── .env.example              # Шаблон переменных → скопировать в .env
    └── init-db.sh                # Инициализация двух БД (auto при старте)
```

---

## Пути приложения

| URL                              | Назначение                  |
|----------------------------------|-----------------------------|
| `https://ontoline.ru/ferag/`     | Vue SPA (frontend)          |
| `https://ontoline.ru/ferag/api/` | FastAPI (REST API)          |
| `https://ontoline.ru/ferag/ws/`  | WebSocket (статусы задач)   |

---

## Порядок запуска (чтобы приложение было доступно в браузере)

1. **nb-win:** поднять PostgreSQL и Fuseki → `docker-compose up -d postgres fuseki` (или сразу `docker-compose up -d`).
2. **cr-ubu:** поднять контейнер ferag (FastAPI + Redis) → `docker-compose up -d`.
3. **nb-win:** поднять worker → `docker-compose up -d worker` (если не поднимали всё одной командой).
4. **По желанию:** на Windows запустить LM Studio (порт 41234) — нужен для RAG/LLM-ответов.

Предварительно: туннель WireGuard, Nginx с конфигом ferag, frontend в `/var/www/ferag/`. Подробно — в [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md#порядок-запуска-приложения).

---

## Развёртывание на cr-ubu

```bash
cd /opt/ferag/deploy/cr-ubu

# 1. Переменные окружения
cp .env.example .env
nano .env  # Заполнить DB_PASSWORD, JWT_SECRET

# 2. Nginx — добавить ferag location блок
sudo cp nginx-location-ferag.conf /etc/nginx/snippets/ferag.conf
sudo nano /etc/nginx/sites-available/ontoline.ru
# В блок server { ... listen 443 ssl ... } добавить:
#     include snippets/ferag.conf;
sudo nginx -t && sudo systemctl reload nginx

# 3. Запустить контейнер
docker-compose up -d

# 4. Проверка
docker-compose ps
curl http://127.0.0.1:47821/ferag/api/health
```

---

## Развёртывание на nb-win

```bash
cd ~/projects/ferag/deploy/nb-win

# 1. Переменные окружения
cp .env.example .env
nano .env  # Заполнить DB_PASSWORD, FUSEKI_PASSWORD

# 2. Запуск
docker-compose up -d

# 3. Проверка
docker-compose ps
docker-compose logs -f worker
```

**Проверка доступности из cr-ubu (через WireGuard):**
```bash
# На cr-ubu:
telnet 10.7.0.3 45432   # PostgreSQL
curl http://10.7.0.3:43030  # Fuseki (если открыт наружу — убрать 127.0.0.1)
```

---

## Порты (экзотические, не конфликтующие)

| Сервис        | Машина  | Порт  | Доступен с           |
|---------------|---------|-------|----------------------|
| FastAPI       | cr-ubu  | 47821 | localhost → Nginx    |
| Redis         | cr-ubu  | 47379 | 10.7.0.1 (WireGuard) |
| PostgreSQL    | nb-win  | 45432 | 10.7.0.3 (WireGuard) |
| Fuseki        | nb-win  | 43030 | localhost nb-win     |
| LM Studio     | nb-win  | 41234 | localhost nb-win     |

---

## Управление

```bash
# Остановка без удаления данных
docker-compose stop

# Остановка + удаление контейнеров (volumes остаются)
docker-compose down

# Пересборка после изменений кода
docker-compose up -d --build
```

---

## Troubleshooting

### Backend не может подключиться к PostgreSQL
```bash
ping 10.7.0.3              # WireGuard работает?
telnet 10.7.0.3 45432      # PostgreSQL слушает?
```

### Worker не видит Redis
```bash
# С nb-win:
ping 10.7.0.1              # WireGuard работает?
redis-cli -h 10.7.0.1 -p 47379 ping
```

### LM Studio недоступен из worker
```bash
docker exec ferag-worker curl http://host.docker.internal:41234/v1/models
# Если не работает — network_mode: host для worker в docker-compose.yml
```
