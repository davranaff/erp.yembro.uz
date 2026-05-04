"""
Переименование display name дефолтной организации «Default» → «YemBro Demo».

Идемпотентно: фильтр по name="Default" — если кто-то уже переименовал
руками, не перетираем.

Системный код `Organization.code = "DEFAULT"` НЕ трогаем — на него
ссылаются ~12 миграций и тестов (Organization.objects.get(code="DEFAULT")).
"""
from django.db import migrations


def rename_default(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Organization.objects.filter(code="DEFAULT", name="Default").update(
        name="YemBro Demo",
    )


def reverse(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Organization.objects.filter(code="DEFAULT", name="YemBro Demo").update(
        name="Default",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("organizations", "0003_organizationmembership_work_phone_and_more"),
    ]

    operations = [
        migrations.RunPython(rename_default, reverse),
    ]
