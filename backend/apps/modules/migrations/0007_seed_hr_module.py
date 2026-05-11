"""
Расширяет Module.kind choices добавляя 'hr' и сидит модуль 'hr' (Кадры и ЗП).
Также включает модуль во всех существующих организациях через OrganizationModule.
"""
from django.db import migrations, models


def add_hr_module(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Organization = apps.get_model("organizations", "Organization")
    OrganizationModule = apps.get_model("modules", "OrganizationModule")

    module, _ = Module.objects.update_or_create(
        code="hr",
        defaults={
            "name": "Кадры и ЗП",
            "kind": "hr",
            "icon": "users",
            "sort_order": 125,
            "is_active": True,
        },
    )
    for org in Organization.objects.all():
        OrganizationModule.objects.update_or_create(
            organization=org, module=module,
            defaults={"is_enabled": True},
        )


def remove_hr_module(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    OrganizationModule = apps.get_model("modules", "OrganizationModule")
    OrganizationModule.objects.filter(module__code="hr").delete()
    Module.objects.filter(code="hr").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("modules", "0006_seed_sales_module"),
    ]

    operations = [
        migrations.AlterField(
            model_name="module",
            name="kind",
            field=models.CharField(
                choices=[
                    ("core", "Ядро"),
                    ("matochnik", "Маточник"),
                    ("incubation", "Инкубация"),
                    ("feedlot", "Фабрика откорма"),
                    ("slaughter", "Убойня"),
                    ("feed", "Корма"),
                    ("vet", "Вет. аптека"),
                    ("stock", "Склад и движения"),
                    ("ledger", "Проводки"),
                    ("reports", "Отчёты"),
                    ("purchases", "Закупки"),
                    ("sales", "Продажи"),
                    ("hr", "Кадры и ЗП"),
                    ("admin", "Администрирование"),
                ],
                max_length=32,
                unique=True,
            ),
        ),
        migrations.RunPython(add_hr_module, remove_hr_module),
    ]
