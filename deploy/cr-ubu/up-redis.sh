#!/bin/bash
# Запуск Redis на cr-ubu (шаг 1.1 плана 26-0219-1110).
# Выполнять на сервере cr-ubu (SSH или консоль), из каталога с проектом:
#   /opt/ferag/deploy/cr-ubu/up-redis.sh
# или из корня репозитория:
#   ./deploy/cr-ubu/up-redis.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
docker compose up -d redis
echo "Redis запущен. Проверка с nb-win: redis-cli -h 10.7.0.1 -p 47379 ping"
