"""
Production setup for the feed module:

1. Remove all generic (no-module) kassas (50.xx, 51.xx subaccounts) and the
   legacy warehouse-kassa markers (КАССА-НАЛ, БАНК-UZS, etc.) from the seed.

2. Create 1 "garbage" write-off warehouse for the feed module (ОТХОД-КОРМ).

3. Create 2 module-scoped kassas:
   - 50.01  Касса · Производство кормов   (module=feed)
   - 50.02  Касса · Убойня                (module=slaughter)

4. Seed raw feed ingredients (NomenclatureItems) as seen in the stock balance:
   макка, соя, бугдой, йог, эрон тухум, матични тухум, хуроз тухум,
   несушка Ф1, извес, биодобавка, гипч, туз, коп.
   Feed-product SKUs (старт/рост/финиш rost308, cargel) are NOT created here.

Idempotent: uses update_or_create / get_or_create throughout.
"""
from django.db import migrations


# ── Raw ingredients (name, sku, unit_code, base_moisture_pct) ──────────────
INGREDIENTS = [
    ("Макка (маккажўхори)",          "RAW-MAKKA",        "kg",   "14.00"),
    ("Соя шроти",                    "RAW-SOYA",         "kg",   "12.00"),
    ("Буғдой (пшеница)",             "RAW-BUGDOY",       "kg",   "14.00"),
    ("Ёғ (ўсимлик мойи)",            "RAW-YOG",          "kg",   None),
    ("Эрон тухуми (инкубацион)",     "RAW-EGG-IRAN",     "pcs",  None),
    ("Маточник тухуми",              "RAW-EGG-PARENT",   "pcs",  None),
    ("Ҳўроз тухуми",                 "RAW-EGG-ROOSTER",  "pcs",  None),
    ("Несушка Ф1",                   "RAW-NESUSHKA-F1",  "head", None),
    ("Оҳактош (известняк)",          "RAW-IZVES",        "kg",   None),
    ("Биологик қўшимча (Bio-Д)",     "RAW-BIODOB",       "kg",   None),
    ("Гипс",                         "RAW-GIPCH",        "kg",   None),
    ("Туз (ош тузи)",                "RAW-TUZ",          "kg",   None),
    ("Коп (таркибий аралашма)",      "RAW-KOP",          "kg",   None),
]

# Legacy kassa-warehouse codes to delete (created by seed_organization YAML)
LEGACY_KASSA_WAREHOUSE_CODES = [
    "КАССА-НАЛ", "БАНК-UZS", "БАНК-USD", "CLICK", "ПЕР-ПУТ",
]

# Generic (no-module) subaccount codes to remove and replace with module-scoped ones
LEGACY_SUBACCOUNT_CODES = ["50.01", "51.01"]


def seed(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    Warehouse = apps.get_model("warehouses", "Warehouse")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    Unit = apps.get_model("nomenclature", "Unit")
    Category = apps.get_model("nomenclature", "Category")
    NomenclatureItem = apps.get_model("nomenclature", "NomenclatureItem")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    modules = {m.code: m for m in Module.objects.all()}
    feed_module = modules.get("feed")
    slaughter_module = modules.get("slaughter")

    # ── 1. Remove legacy kassa warehouses ────────────────────────────────────
    Warehouse.objects.filter(
        organization=org,
        code__in=LEGACY_KASSA_WAREHOUSE_CODES,
    ).delete()

    # ── 2. Remove generic (no-module) kassas ─────────────────────────────────
    # Only delete subaccounts that have NO module (the generic seeded ones).
    # If someone already linked them to a module, leave them alone.
    GLSubaccount.objects.filter(
        account__organization=org,
        code__in=LEGACY_SUBACCOUNT_CODES,
        module__isnull=True,
    ).delete()

    # ── 3. Create garbage write-off warehouse for feed ────────────────────────
    if feed_module:
        Warehouse.objects.get_or_create(
            organization=org,
            code="ОТХОД-КОРМ",
            defaults={
                "name": "Корм · Отходы производства",
                "module": feed_module,
                "is_active": True,
            },
        )

    # ── 4. Create module-scoped kassas ────────────────────────────────────────
    try:
        account_50 = GLAccount.objects.get(organization=org, code="50")
    except GLAccount.DoesNotExist:
        account_50 = None

    if account_50 and feed_module:
        GLSubaccount.objects.update_or_create(
            account=account_50,
            code="50.01",
            defaults={
                "name": "Касса · Производство кормов",
                "module": feed_module,
            },
        )
    if account_50 and slaughter_module:
        GLSubaccount.objects.update_or_create(
            account=account_50,
            code="50.02",
            defaults={
                "name": "Касса · Убойня",
                "module": slaughter_module,
            },
        )

    # ── 5. Ensure units exist ─────────────────────────────────────────────────
    units_map = {}
    for code, name in [("kg", "Килограмм"), ("pcs", "Штука"), ("head", "Голова")]:
        unit, _ = Unit.objects.get_or_create(
            organization=org, code=code, defaults={"name": name}
        )
        units_map[code] = unit

    # ── 6. Ensure raw-materials category exists ───────────────────────────────
    raw_category, _ = Category.objects.get_or_create(
        organization=org,
        name="Сырьё для кормов",
        defaults={"module": feed_module},
    )

    # Sub-account 10.01 (raw materials) — used as default GL for ingredients
    sub_10_01 = GLSubaccount.objects.filter(
        account__organization=org, code="10.01"
    ).first()

    # ── 7. Seed raw ingredients ───────────────────────────────────────────────
    for name, sku, unit_code, moisture in INGREDIENTS:
        unit = units_map.get(unit_code)
        if unit is None:
            continue
        NomenclatureItem.objects.update_or_create(
            organization=org,
            sku=sku,
            defaults={
                "name": name,
                "category": raw_category,
                "unit": unit,
                "default_gl_subaccount": sub_10_01,
                "base_moisture_pct": moisture,
                "is_active": True,
            },
        )


def reverse(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Warehouse = apps.get_model("warehouses", "Warehouse")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    NomenclatureItem = apps.get_model("nomenclature", "NomenclatureItem")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    Warehouse.objects.filter(organization=org, code="ОТХОД-КОРМ").delete()
    GLSubaccount.objects.filter(
        account__organization=org, code__in=["50.01", "50.02"]
    ).delete()
    NomenclatureItem.objects.filter(
        organization=org,
        sku__in=[row[1] for row in INGREDIENTS],
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("rbac", "0013_seed_production_users"),
        ("accounting", "0013_seed_70_01_subaccount"),
        ("warehouses", "0006_stockmovement_shrinkage_kind"),
        ("nomenclature", "0006_seed_module_categories"),
    ]

    operations = [
        migrations.RunPython(seed, reverse),
    ]
