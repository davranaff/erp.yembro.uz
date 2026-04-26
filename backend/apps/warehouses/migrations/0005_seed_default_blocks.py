"""
Сидер дефолтных производственных блоков для DEFAULT-org для модулей,
где их нет: feedlot (птичник) и slaughter (линия разделки).

Без этих блоков нельзя создать FeedlotBatch (поле house_block) и
SlaughterShift (поле line_block) — формы блокируются.

Идемпотентно — пропускает если блок такого типа уже существует.
"""
from django.db import migrations


# (module_code, kind, code, name)
# Префикс DEF- чтобы не конфликтовать с кодами в тестовых фикстурах.
DEFAULT_BLOCKS = [
    ("feedlot",   "feedlot",        "DEF-ПТ-1",  "Птичник №1"),
    ("slaughter", "slaughter_line", "DEF-ЛН-1",  "Линия разделки №1"),
]


def seed_blocks(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    ProductionBlock = apps.get_model("warehouses", "ProductionBlock")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    for module_code, kind, code, name in DEFAULT_BLOCKS:
        module = Module.objects.filter(code=module_code).first()
        if module is None:
            continue
        # Пропускаем если уже есть блок такого типа в этом модуле
        if ProductionBlock.objects.filter(
            organization=org, module=module, kind=kind, is_active=True,
        ).exists():
            continue
        ProductionBlock.objects.get_or_create(
            organization=org,
            code=code,
            defaults={
                "module": module,
                "name": name,
                "kind": kind,
                "is_active": True,
            },
        )


def unseed_blocks(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0004_seed_default_warehouses"),
    ]

    operations = [
        migrations.RunPython(seed_blocks, unseed_blocks),
    ]
