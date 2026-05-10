"""
Сидер государственных праздников Узбекистана на 2026 год.
organization=None — глобальные.

Источник: Трудовой кодекс РУз + указ президента о выходных днях.
Если даты переносятся (выпадают на выходной — переносятся на след. рабочий день),
HR-админ может скорректировать через /admin или /api/payroll/holidays/.
"""
from django.db import migrations


UZ_HOLIDAYS_2026 = [
    ("2026-01-01", "Новый год"),
    ("2026-01-02", "Новый год"),
    ("2026-03-08", "Международный женский день"),
    ("2026-03-21", "Навруз"),
    ("2026-05-09", "День памяти и почестей"),
    ("2026-09-01", "День независимости"),
    ("2026-10-01", "День учителей и наставников"),
    ("2026-12-08", "День Конституции"),
    # Религиозные (даты ежегодно сдвигаются — корректируйте вручную):
    ("2026-03-21", "Навруз"),  # совпадает с Навруз
    ("2026-03-31", "Рамазан хайит"),  # Eid al-Fitr 2026 (примерная дата)
    ("2026-06-07", "Курбан хайит"),    # Eid al-Adha 2026 (примерная дата)
]


def seed_holidays(apps, schema_editor):
    Holiday = apps.get_model("payroll", "Holiday")
    seen = set()
    for date_str, name in UZ_HOLIDAYS_2026:
        if date_str in seen:
            continue
        seen.add(date_str)
        Holiday.objects.update_or_create(
            organization=None, date=date_str,
            defaults={"name": name, "is_paid": True},
        )


def unseed_holidays(apps, schema_editor):
    Holiday = apps.get_model("payroll", "Holiday")
    Holiday.objects.filter(organization__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("payroll", "0005_holiday"),
    ]

    operations = [
        migrations.RunPython(seed_holidays, unseed_holidays),
    ]
