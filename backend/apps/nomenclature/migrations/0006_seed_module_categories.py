"""
Создаёт базовые категории номенклатуры с привязкой к модулям.

Существующая категория «Готовая продукция убоя» (из 0004) обновляется —
ставится module=slaughter. Это нужно чтобы фильтр `?module_code=slaughter`
работал в формах убойни.

Также сидируются категории-заглушки для остальных производственных модулей
чтобы пользователь мог сразу класть SKU «в модуль».
"""
from django.db import migrations


# (module_code, category_name) — будут созданы (или обновлены если уже есть)
MODULE_CATEGORIES = [
    ("matochnik",  "Маточник · сырьё и продукция"),
    ("incubation", "Инкубация · яйцо и цыплята"),
    ("feedlot",    "Откорм · живая птица"),
    ("slaughter",  "Готовая продукция убоя"),  # уже создана в 0004 — обновим module
    ("feed",       "Корма · сырьё и готовые"),
    ("vet",        "Ветпрепараты"),
]


def seed_categories(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    Category = apps.get_model("nomenclature", "Category")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    modules = {m.code: m for m in Module.objects.all()}

    for module_code, cat_name in MODULE_CATEGORIES:
        module = modules.get(module_code)
        if module is None:
            continue
        Category.objects.update_or_create(
            organization=org,
            name=cat_name,
            defaults={"module": module},
        )


def unseed_categories(apps, schema_editor):
    # Не удаляем — могут быть привязки в NomenclatureItem.category.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("nomenclature", "0005_category_module_and_more"),
        ("modules", "0006_seed_sales_module"),
    ]

    operations = [
        migrations.RunPython(seed_categories, unseed_categories),
    ]
