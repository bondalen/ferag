#!/usr/bin/env python3
"""Анализ результатов индексации GraphRAG"""

import pandas as pd
import json

print("=" * 80)
print("АНАЛИЗ РЕЗУЛЬТАТОВ ИНДЕКСАЦИИ GRAPHRAG")
print("=" * 80)

# 1. Entities (сущности)
print("\n1. СУЩНОСТИ (entities.parquet)")
print("-" * 80)
entities = pd.read_parquet('output/entities.parquet')
print(f"Всего сущностей: {len(entities)}")
print(f"\nКолонки: {list(entities.columns)}")
print(f"\nПример первых 3 сущностей:")
print(entities[['title', 'type', 'description']].head(3).to_string())

# Группировка по типам
if 'type' in entities.columns:
    print(f"\n\nСущности по типам:")
    type_counts = entities['type'].value_counts()
    for entity_type, count in type_counts.items():
        print(f"  {entity_type}: {count}")

# 2. Relationships (связи)
print("\n\n2. СВЯЗИ (relationships.parquet)")
print("-" * 80)
relationships = pd.read_parquet('output/relationships.parquet')
print(f"Всего связей: {len(relationships)}")
print(f"\nКолонки: {list(relationships.columns)}")
print(f"\nПример первых 3 связей:")
if 'source' in relationships.columns and 'target' in relationships.columns:
    print(relationships[['source', 'target', 'description']].head(3).to_string())

# 3. Communities (сообщества)
print("\n\n3. СООБЩЕСТВА (communities.parquet)")
print("-" * 80)
communities = pd.read_parquet('output/communities.parquet')
print(f"Всего сообществ: {len(communities)}")
print(f"\nКолонки: {list(communities.columns)}")
print(f"\nСообщества по уровням:")
if 'level' in communities.columns:
    level_counts = communities['level'].value_counts().sort_index()
    for level, count in level_counts.items():
        print(f"  Уровень {level}: {count} сообществ")

# 4. Community Reports (отчеты по сообществам)
print("\n\n4. ОТЧЕТЫ ПО СООБЩЕСТВАМ (community_reports.parquet)")
print("-" * 80)
reports = pd.read_parquet('output/community_reports.parquet')
print(f"Всего отчетов: {len(reports)}")
print(f"\nКолонки: {list(reports.columns)}")
if 'level' in reports.columns:
    level_counts = reports['level'].value_counts().sort_index()
    print(f"\nОтчеты по уровням:")
    for level, count in level_counts.items():
        print(f"  Уровень {level}: {count} отчетов")

# Показать пример отчета
if 'title' in reports.columns and 'summary' in reports.columns:
    print(f"\n\nПример отчета (уровень 1):")
    level1_reports = reports[reports['level'] == 1]
    if len(level1_reports) > 0:
        first_report = level1_reports.iloc[0]
        print(f"Название: {first_report['title']}")
        print(f"Краткое содержание: {first_report['summary'][:200]}...")

# 5. Text Units (текстовые единицы)
print("\n\n5. ТЕКСТОВЫЕ ЕДИНИЦЫ (text_units.parquet)")
print("-" * 80)
text_units = pd.read_parquet('output/text_units.parquet')
print(f"Всего текстовых единиц: {len(text_units)}")
print(f"\nКолонки: {list(text_units.columns)}")

# 6. Documents (документы)
print("\n\n6. ДОКУМЕНТЫ (documents.parquet)")
print("-" * 80)
documents = pd.read_parquet('output/documents.parquet')
print(f"Всего документов: {len(documents)}")
print(f"\nКолонки: {list(documents.columns)}")
if 'title' in documents.columns:
    print(f"\nСписок документов:")
    for idx, doc in documents.iterrows():
        print(f"  - {doc['title']}")

print("\n" + "=" * 80)
print("ИТОГОВАЯ СТАТИСТИКА")
print("=" * 80)
print(f"Документов: {len(documents)}")
print(f"Текстовых единиц: {len(text_units)}")
print(f"Сущностей: {len(entities)}")
print(f"Связей: {len(relationships)}")
print(f"Сообществ: {len(communities)}")
print(f"Отчетов по сообществам: {len(reports)}")
print("=" * 80)
