"""
Добавляет модуль `sales` (Продажи) — для RBAC прав на /sales и audit.
"""
from django.db import migrations


def add_sales_module(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Module.objects.update_or_create(
        code="sales",
        defaults={
            "name": "Продажи",
            "kind": "sales",
            "icon": "cart",
            "sort_order": 105,
            "is_active": True,
        },
    )


def remove_sales_module(apps, schema_editor):
    Module = apps.get_model("modules", "Module")
    Module.objects.filter(code="sales").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("modules", "0005_alter_module_kind"),
    ]

    operations = [
        migrations.RunPython(add_sales_module, remove_sales_module),
    ]
