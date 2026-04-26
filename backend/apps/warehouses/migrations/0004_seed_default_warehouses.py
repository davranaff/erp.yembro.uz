"""
Сидер дефолтных складов для DEFAULT-org по всем продуктовым модулям.

Создаёт по одному активному складу на модуль если его ещё нет:
    matochnik    · СК-М     · Склад маточника
    incubation   · СК-И     · Склад инкубации
    feedlot      · СК-Ф     · Склад откорма
    slaughter    · СК-У-ГП  · Склад готовой продукции (убой)
    feed         · СК-К     · Склад кормов

Без этих складов межмодульные транзферы (matochnik→incubation→feedlot→slaughter)
падают с ошибкой «Не найден активный склад модуля 'X'».

Идемпотентно: пропускает существующие склады по (organization, code) или
если для модуля уже есть хотя бы один активный склад — ничего не создаёт.
"""
from django.db import migrations


# (module_code, default_code, default_name)
# Префикс DEF- чтобы не конфликтовать с кодами в тестовых фикстурах.
DEFAULT_WAREHOUSES = [
    ("matochnik",  "DEF-СК-М",   "Склад маточника"),
    ("incubation", "DEF-СК-И",   "Склад инкубации"),
    ("feedlot",    "DEF-СК-Ф",   "Склад откорма"),
    ("slaughter",  "DEF-СК-ГП",  "Склад готовой продукции (убой)"),
    ("feed",       "DEF-СК-К",   "Склад кормов"),
]


def seed_warehouses(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    Warehouse = apps.get_model("warehouses", "Warehouse")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    for module_code, code, name in DEFAULT_WAREHOUSES:
        module = Module.objects.filter(code=module_code).first()
        if module is None:
            continue
        # Пропускаем если уже есть активный склад этого модуля
        if Warehouse.objects.filter(
            organization=org, module=module, is_active=True
        ).exists():
            continue
        Warehouse.objects.get_or_create(
            organization=org,
            code=code,
            defaults={
                "module": module,
                "name": name,
                "is_active": True,
            },
        )


def unseed_warehouses(apps, schema_editor):
    # Откат не удаляет — могут быть привязки в StockMovement.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("warehouses", "0003_alter_productionblock_kind"),
        ("organizations", "0001_initial"),
        ("modules", "0006_seed_sales_module"),
    ]

    operations = [
        migrations.RunPython(seed_warehouses, unseed_warehouses),
    ]
