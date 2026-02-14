#!/bin/bash
# 4.2. Загрузка RDF цикла 2 в Apache Jena Fuseki
# Использование:
#   ./load_to_fuseki_cycle2.sh [DATASET] [TTL_FILE]
# По умолчанию: ferag-staging-cycle2, ../graphrag-test-cycle2/graphrag_output_cycle2.ttl
# Для онтологии: ./load_to_fuseki_cycle2.sh ferag-ontology-cycle2 ../graphrag-test-cycle2/extracted_ontology_cycle2.ttl

set -e
FUSEKI="${FUSEKI_URL:-http://localhost:3030}"
AUTH="${FUSEKI_AUTH:-admin:ferag2026}"
DS="${1:-ferag-staging-cycle2}"
TTL="${2:-../graphrag-test-cycle2/graphrag_output_cycle2.ttl}"

if [ ! -f "$TTL" ]; then
  echo "Файл не найден: $TTL"
  exit 1
fi

STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$FUSEKI/\$\/datasets" -u "$AUTH" \
  -H "Content-Type: application/x-www-form-urlencoded" -d "dbType=tdb2&dbName=$DS")
if [ "$STATUS" != "200" ] && [ "$STATUS" != "400" ]; then
  echo "Ошибка создания dataset $DS: HTTP $STATUS. Проверьте Fuseki: $FUSEKI"
  exit 1
fi

# PUT для замены default graph (POST на этом Fuseki даёт 405)
curl -s -X PUT "$FUSEKI/$DS/data" -u "$AUTH" \
  -H "Content-Type: text/turtle" --data-binary @"$TTL"
echo ""
echo "Готово. Dataset: $DS. Проверка: $FUSEKI → Query"
