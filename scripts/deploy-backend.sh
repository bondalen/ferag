#!/usr/bin/env bash
# Быстрый деплой backend (образ ferag-backend:latest) на cr-ubu.
# Запуск из корня репозитория: ./scripts/deploy-backend.sh
# Требуется: Docker, SSH к cr-ubu под cursor-agent (ключ .ssh/cursor_agent_key).
# На cr-ubu в ~/ferag-deploy/ должен быть актуальный .env (хосты 10.7.0.3).
# См. deploy/DEPLOYMENT_SUMMARY.md

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DEPLOY_HOST="${DEPLOY_HOST:-176.108.244.252}"
SSH_KEY="${SSH_KEY:-$REPO_ROOT/.ssh/cursor_agent_key}"
KNOWN_HOSTS="${KNOWN_HOSTS:-$REPO_ROOT/.ssh/known_hosts}"
REMOTE_USER="cursor-agent"
REMOTE_TAR="/tmp/ferag-backend.tar.gz"

echo "Build backend image..."
docker build -t ferag-backend:latest -f code/backend/Dockerfile code/backend/

echo "Export image..."
docker save ferag-backend:latest | gzip > /tmp/ferag-backend.tar.gz

echo "Upload image to ${REMOTE_USER}@${DEPLOY_HOST}..."
scp -i "$SSH_KEY" -o "UserKnownHostsFile=$KNOWN_HOSTS" /tmp/ferag-backend.tar.gz "${REMOTE_USER}@${DEPLOY_HOST}:${REMOTE_TAR}"

echo "Load image and restart ferag container..."
ssh -i "$SSH_KEY" -o "UserKnownHostsFile=$KNOWN_HOSTS" "${REMOTE_USER}@${DEPLOY_HOST}" 'bash -s' << 'REMOTE'
set -e
docker load < /tmp/ferag-backend.tar.gz
REDIS_IP=$(docker inspect ferag-redis --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}')
cd ~/ferag-deploy && set -a && . ./.env && set +a
export REDIS_URL="redis://${REDIS_IP}:47379/0"
export CELERY_BROKER_URL="redis://${REDIS_IP}:47379/0"
export CELERY_RESULT_BACKEND="redis://${REDIS_IP}:47379/1"
docker stop ferag 2>/dev/null || true
docker rm ferag 2>/dev/null || true
docker run -d --name ferag --restart unless-stopped --network bridge -p 127.0.0.1:47821:47821 \
  -e DATABASE_URL="$DATABASE_URL" \
  -e REDIS_URL="$REDIS_URL" \
  -e CELERY_BROKER_URL="$CELERY_BROKER_URL" \
  -e CELERY_RESULT_BACKEND="$CELERY_RESULT_BACKEND" \
  -e JWT_SECRET="$JWT_SECRET" \
  -e FUSEKI_URL="$FUSEKI_URL" \
  -e FUSEKI_USER="$FUSEKI_USER" \
  -e FUSEKI_PASSWORD="$FUSEKI_PASSWORD" \
  -e ALLOWED_ORIGINS="${ALLOWED_ORIGINS:-https://ontoline.ru}" \
  -e LLM_API_URL="${LLM_API_URL:-http://10.7.0.3:1234/v1}" \
  -e LLM_MODEL="${LLM_MODEL:-llama-3.3-70b-instruct}" \
  ferag-backend:latest
echo "Backend container restarted."
REMOTE

rm -f /tmp/ferag-backend.tar.gz
echo "Backend deploy done. Check https://ontoline.ru/ferag/"
echo "Optional: remove image on server: ssh ... 'rm /tmp/ferag-backend.tar.gz'"
