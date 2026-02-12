#!/usr/bin/env python3
"""Просмотр отчетов по сообществам"""

import pandas as pd

print("=" * 80)
print("ОТЧЕТЫ ПО СООБЩЕСТВАМ - ДЕТАЛЬНЫЙ ПРОСМОТР")
print("=" * 80)

reports = pd.read_parquet('output/community_reports.parquet')

# Сортируем по уровню и рейтингу
reports_sorted = reports.sort_values(['level', 'rank'], ascending=[True, False])

for idx, report in reports_sorted.iterrows():
    print(f"\n{'=' * 80}")
    print(f"УРОВЕНЬ: {report['level']} | РЕЙТИНГ: {report['rank']:.1f}")
    print(f"НАЗВАНИЕ: {report['title']}")
    print(f"{'=' * 80}")
    print(f"\nКРАТКОЕ СОДЕРЖАНИЕ:")
    print(report['summary'])
    print(f"\n{'-' * 80}")
    
print("\n" + "=" * 80)
