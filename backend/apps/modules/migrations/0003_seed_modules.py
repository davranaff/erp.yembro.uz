from django.db import migrations

MODULES = [
    ("core", "Ядро", "core", "layers", 10),
    ("matochnik", "Маточник", "matochnik", "feather", 20),
    ("incubation", "Инкубация", "incubation", "egg", 30),
    ("feedlot", "Фабрика откорма", "feedlot", "factory", 40),
    ("slaughter", "Убойня", "slaughter", "scissors", 50),
    ("feed", "Корма", "feed", "bag", 60),
    ("vet", "Вет. аптека", "vet", "pharma", 70),
    ("stock", "Склад и движения", "stock", "box", 80),
    ("ledger", "Проводки", "ledger", "book", 90),
    ("purchases", "Закупки", "purchases", "cart", 100),
    ("reports", "Отчёты", "reports", "chart", 110),
    ("admin", "Администрирование", "admin", "settings", 120),
]


def seed_modules(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    for code, name, kind, icon, sort_order in MODULES:
        Module.objects.update_or_create(
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "icon": icon,
                "sort_order": sort_order,
                "is_active": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [
        ("modules", "0002_initial"),
    ]

    operations = [
        migrations.RunPython(seed_modules, migrations.RunPython.noop),
    ]
