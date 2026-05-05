"""
Добавить план счёт 41 «Товары для перепродажи» + субсчёт 41.01.

Используется для аксессуаров вет-аптеки (миски, поилки, переноски и т.п.) —
вещи которые не лекарства и не корма, а просто товары для перепродажи через
розницу. Отделено от 10.03 (ветпрепараты) чтобы остатки не мешались в
отчётах и весь movement шёл по своему счёту.

При желании сюда же можно вешать любые другие товары для перепродажи
(спецодежда, тара и т.п.) — счёт общий, не привязан к модулю vet.
"""
from django.db import migrations


def seed_account(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    account, _ = GLAccount.objects.update_or_create(
        organization=org,
        code="41",
        defaults={"name": "Товары для перепродажи", "type": "asset"},
    )
    GLSubaccount.objects.update_or_create(
        account=account,
        code="41.01",
        defaults={"name": "Товары для перепродажи", "module": None},
    )


def remove_account(apps, schema_editor):
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount.objects.filter(code="41.01").delete()
    GLAccount.objects.filter(code="41").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0011_seed_71_subaccount"),
        ("organizations", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_account, remove_account),
    ]
