"""
Сидер номенклатуры готовой продукции убоя для DEFAULT-org.

Создаёт категорию «Готовая продукция убоя» и базовый набор SKU:
    CARCASS-WHOLE / BREAST / LEG / WING / OFFAL / FEET / HEAD / NECK

Идемпотентно по (org, sku) и (org, name категории).
"""
from django.db import migrations


SLAUGHTER_CATEGORY_NAME = "Готовая продукция убоя"
SLAUGHTER_GL_CODE = "43.01"
SLAUGHTER_UNIT_CODE = "kg"

# (sku, name)
SLAUGHTER_SKUS = [
    ("CARCASS-WHOLE", "Тушка целая"),
    ("BREAST",        "Грудка"),
    ("LEG",           "Окорочка"),
    ("WING",          "Крылья"),
    ("OFFAL",         "Субпродукты"),
    ("FEET",          "Лапки"),
    ("HEAD",          "Головы"),
    ("NECK",          "Шеи"),
]


def seed_slaughter_skus(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Unit = apps.get_model("nomenclature", "Unit")
    Category = apps.get_model("nomenclature", "Category")
    NomenclatureItem = apps.get_model("nomenclature", "NomenclatureItem")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    # Юнит kg должен быть посеян раньше (валидно для DEFAULT-org)
    unit_kg = Unit.objects.filter(organization=org, code=SLAUGHTER_UNIT_CODE).first()
    if unit_kg is None:
        # Без kg продолжать нет смысла — пропустим (создадим стандартно при инициализации org)
        unit_kg, _ = Unit.objects.get_or_create(
            organization=org,
            code=SLAUGHTER_UNIT_CODE,
            defaults={"name": "Килограмм"},
        )

    # Субсчёт 43.01 (готовая продукция)
    fg_sub = (
        GLSubaccount.objects.filter(
            account__organization=org, code=SLAUGHTER_GL_CODE
        ).first()
    )

    category, _ = Category.objects.get_or_create(
        organization=org,
        name=SLAUGHTER_CATEGORY_NAME,
        defaults={"default_gl_subaccount": fg_sub},
    )
    if fg_sub and category.default_gl_subaccount_id != fg_sub.id:
        category.default_gl_subaccount = fg_sub
        category.save(update_fields=["default_gl_subaccount"])

    for sku, name in SLAUGHTER_SKUS:
        NomenclatureItem.objects.update_or_create(
            organization=org,
            sku=sku,
            defaults={
                "name": name,
                "category": category,
                "unit": unit_kg,
                "default_gl_subaccount": fg_sub,
                "is_active": True,
            },
        )


def unseed_slaughter_skus(apps, schema_editor):
    # Откат не удаляет SKU, чтобы не сломать существующие проводки/выходы.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("nomenclature", "0003_nomenclatureitem_base_moisture_pct"),
        ("organizations", "0001_initial"),
        ("accounting", "0009_seed_expense_articles"),
    ]

    operations = [
        migrations.RunPython(seed_slaughter_skus, unseed_slaughter_skus),
    ]
