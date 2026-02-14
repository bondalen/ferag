#!/bin/bash
# 4.5. Обновление production: ferag-prod = результирующая онтология + результирующий массив триплетов
# Требует: Fuseki запущен, файлы integrated_ontology.ttl и integrated_triples.ttl в graphrag-test
# Использование: из каталога graphrag-test запустить bash load_to_prod.sh

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
FUSEKI="${FUSEKI_URL:-http://localhost:3030}"
AUTH="${FUSEKI_AUTH:-admin:ferag2026}"
DS="ferag-prod"
ONTOLOGY="${ROOT}/integrated_ontology.ttl"
TRIPLES="${ROOT}/integrated_triples.ttl"
MERGED="${ROOT}/prod_merged.ttl"

if [ ! -f "$ONTOLOGY" ]; then
  echo "Не найден: $ONTOLOGY"
  exit 1
fi
if [ ! -f "$TRIPLES" ]; then
  echo "Не найден: $TRIPLES"
  exit 1
fi

echo "Объединение онтологии и триплетов..."
python3 -c "
from rdflib import Graph
g = Graph()
g.parse('$ONTOLOGY', format='turtle')
g.parse('$TRIPLES', format='turtle')
g.serialize(destination='$MERGED', format='turtle', encoding='utf-8')
print(f'Записано {len(g)} триплетов в $MERGED')
"

echo "Создание датасета $DS..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$FUSEKI/\$\/datasets" -u "$AUTH" \
  -H "Content-Type: application/x-www-form-urlencoded" -d "dbType=tdb2&dbName=$DS")
if [ "$STATUS" != "200" ] && [ "$STATUS" != "400" ]; then
  echo "Ошибка создания dataset: HTTP $STATUS. Fuseki: $FUSEKI"
  exit 1
fi

echo "Загрузка в $DS/data (PUT)..."
curl -s -X PUT "$FUSEKI/$DS/data" -u "$AUTH" \
  -H "Content-Type: text/turtle" --data-binary @"$MERGED"
echo ""
echo "Готово. Production: $FUSEKI → Dataset: $DS → Query"
echo "При необходимости включите OWL/RDFS reasoning в настройках датасета $DS."
