#!/usr/bin/env bash
# Быстрый деплой frontend на cr-ubu.
# Запуск из корня репозитория: ./scripts/deploy-frontend.sh
#
# Режимы:
# 1) DEPLOY_USE_CURSOR_AGENT=1 (или DEPLOY_USER=cursor-agent) — для AI-агента:
#    использует ключ .ssh/cursor_agent_key, пишет в ~/ferag-www на cr-ubu.
#    На сервере один раз: /var/www/ferag должен быть симлинком на ~cursor-agent/ferag-www
#    (см. deploy/DEPLOYMENT_SUMMARY.md, раздел «Деплой силами агента»).
# 2) По умолчанию (user1) — загрузка в /tmp и sudo cp в /var/www/ferag (нужен доступ user1).
# См. deploy/DEPLOYMENT_SUMMARY.md

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

DEPLOY_HOST="${DEPLOY_HOST:-176.108.244.252}"
DEPLOY_USER="${DEPLOY_USER:-user1}"
SSH_KEY="${SSH_KEY:-$REPO_ROOT/.ssh/cursor_agent_key}"
KNOWN_HOSTS="${KNOWN_HOSTS:-$REPO_ROOT/.ssh/known_hosts}"

# Режим «только cursor-agent»: агент может выполнить скрипт без user1 и sudo
if [[ -n "${DEPLOY_USE_CURSOR_AGENT}" ]] || [[ "$DEPLOY_USER" == "cursor-agent" ]]; then
  DEPLOY_USER="cursor-agent"
  REMOTE_PATH="ferag-www"
  SSH_OPTS=(-o "UserKnownHostsFile=$KNOWN_HOSTS")
  [[ -f "$SSH_KEY" ]] && SSH_OPTS=(-i "$SSH_KEY" "${SSH_OPTS[@]}")
  RSYNC_RSH="ssh ${SSH_OPTS[*]}"
  echo "Build frontend..."
  cd code/frontend
  npm run build
  cd "$REPO_ROOT"
  echo "Upload dist to ${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_PATH}/ (cursor-agent mode)..."
  rsync -avz --delete -e "$RSYNC_RSH" code/frontend/dist/ "${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_PATH}/"
  echo "Frontend deploy done (agent mode). Check https://ontoline.ru/ferag/"
  exit 0
fi

REMOTE_TMP="/tmp/ferag-frontend"
echo "Build frontend..."
cd code/frontend
npm run build
cd "$REPO_ROOT"
echo "Upload dist to ${DEPLOY_USER}@${DEPLOY_HOST}..."
rsync -avz --delete -e "ssh" code/frontend/dist/ "${DEPLOY_USER}@${DEPLOY_HOST}:${REMOTE_TMP}/"
echo "Copy to /var/www/ferag and fix ownership..."
ssh "${DEPLOY_USER}@${DEPLOY_HOST}" "sudo cp -r ${REMOTE_TMP}/* /var/www/ferag/ && sudo chown -R www-data:www-data /var/www/ferag && rm -rf ${REMOTE_TMP}"
echo "Frontend deploy done. Check https://ontoline.ru/ferag/"
