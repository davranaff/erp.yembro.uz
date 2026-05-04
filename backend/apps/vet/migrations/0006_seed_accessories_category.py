"""
Засеять категорию «Аксессуары вет-аптеки» (module=vet) для DEFAULT org.

Без этого пользователь, открыв форму «Новый аксессуар», увидит в дропдауне
номенклатуры только препараты — категории под аксессуары нет, и куда их
плодить непонятно. Создаём дефолтную категорию с привязкой к 41.01,
чтобы создание новых SKU «миска / поилка» было очевидным.
"""
from django.db import migrations


CATEGORY_NAME = "Аксессуары вет-аптеки"


def seed_category(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    Category = apps.get_model("nomenclature", "Category")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    try:
        vet_module = Module.objects.get(code="vet")
    except Module.DoesNotExist:
        return

    sub = GLSubaccount.objects.filter(
        account__organization=org, code="41.01"
    ).first()

    Category.objects.update_or_create(
        organization=org,
        name=CATEGORY_NAME,
        defaults={
            "module": vet_module,
            "default_gl_subaccount": sub,
        },
    )


def remove_category(apps, schema_editor):
    Category = apps.get_model("nomenclature", "Category")
    Category.objects.filter(name=CATEGORY_NAME).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("vet", "0005_vetaccessory"),
        ("nomenclature", "0001_initial"),
        ("modules", "0003_seed_modules"),
        ("accounting", "0012_seed_41_goods_for_resale"),
    ]

    operations = [
        migrations.RunPython(seed_category, remove_category),
    ]
