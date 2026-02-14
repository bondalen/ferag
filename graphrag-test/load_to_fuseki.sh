#!/bin/bash
# 2.9. Загрузка graphrag_output.ttl в Apache Jena Fuseki (dataset ferag-staging)
# Требует: Fuseki запущен (docker start fuseki), файл graphrag_output.ttl в текущем каталоге
# Использование: из каталога graphrag-test запустить ./load_to_fuseki.sh

set -e
FUSEKI="${FUSEKI_URL:-http://localhost:3030}"
AUTH="${FUSEKI_AUTH:-admin:ferag2026}"
TTL="${1:-graphrag_output.ttl}"

if [ ! -f "$TTL" ]; then
  echo "Создайте сначала graphrag_output.ttl: python test_graphrag_to_rdf.py"
  exit 1
fi

# Создать dataset, если ещё нет (200 = создан, 400 = уже есть)
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$FUSEKI/\$\/datasets" -u "$AUTH" \
  -H "Content-Type: application/x-www-form-urlencoded" -d "dbType=tdb2&dbName=ferag-staging")
if [ "$STATUS" != "200" ] && [ "$STATUS" != "400" ]; then
  echo "Ошибка создания dataset: HTTP $STATUS. Проверьте, что Fuseki запущен: $FUSEKI"
  exit 1
fi

# Загрузить Turtle
curl -s -X POST "$FUSEKI/ferag-staging/data" -u "$AUTH" \
  -H "Content-Type: text/turtle" --data-binary @"$TTL"
echo ""
echo "Готово. Проверка: $FUSEKI → Dataset: ferag-staging → Query"
