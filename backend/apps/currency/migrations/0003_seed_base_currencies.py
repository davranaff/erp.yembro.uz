"""
Гарантировать наличие базовых валют UZS и USD в справочнике.

Обычно они досеиваются CBU-fetcher-ом (apps.currency.services.cbu), но
на fresh-БД до первой синхронизации приложению всё равно нужно уметь
работать с этими двумя кодами (UZS — accounting_currency по умолчанию;
USD — самая частая импортная валюта).
"""
from django.db import migrations


BASE_CURRENCIES = [
    # (code, numeric, name_ru, name_en)
    ("UZS", "860", "Узбекский сум", "Uzbek Sum"),
    ("USD", "840", "Доллар США", "US Dollar"),
]


def seed_base_currencies(apps, schema_editor):
    Currency = apps.get_model("currency", "Currency")
    for code, numeric, name_ru, name_en in BASE_CURRENCIES:
        Currency.objects.update_or_create(
            code=code,
            defaults={
                "numeric_code": numeric,
                "name_ru": name_ru,
                "name_en": name_en,
                "is_active": True,
            },
        )


def noop(apps, schema_editor):
    # Сохраняем валюты при откате — они могут быть залинкованы в PO/Payment/SO.
    return


class Migration(migrations.Migration):
    dependencies = [
        ("currency", "0002_seed_cbu_beat"),
    ]

    operations = [
        migrations.RunPython(seed_base_currencies, noop),
    ]
