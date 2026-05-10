"""
Добавляет субсчёт 70.01 «Расчёты с персоналом по оплате труда» в план счетов
DEFAULT-организации. Используется для зарплатных платежей: Дт 70.01 / Кт 50|51.

Также прокидывает default_subaccount=70.01 в ExpenseArticle(code="SALARY"),
если оно ещё не привязано — миграция 0009_seed_expense_articles создавала
статью SALARY со ссылкой на код "70.01", который тогда не существовал.
"""
from django.db import migrations


def add_70_account(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    ExpenseArticle = apps.get_model("accounting", "ExpenseArticle")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    parent, _ = GLAccount.objects.update_or_create(
        organization=org,
        code="70",
        defaults={"name": "Расчёты с персоналом по оплате труда", "type": "liability"},
    )
    sub_70_01, _ = GLSubaccount.objects.update_or_create(
        account=parent,
        code="70.01",
        defaults={"name": "Расчёты с персоналом по оплате труда (UZS)"},
    )
    ExpenseArticle.objects.filter(
        organization=org, code="SALARY", default_subaccount__isnull=True
    ).update(default_subaccount=sub_70_01)


def remove_70_account(apps, schema_editor):
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    ExpenseArticle = apps.get_model("accounting", "ExpenseArticle")

    ExpenseArticle.objects.filter(
        code="SALARY", default_subaccount__code="70.01"
    ).update(default_subaccount=None)
    GLSubaccount.objects.filter(code="70.01").delete()
    GLAccount.objects.filter(code="70").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0012_seed_41_goods_for_resale"),
    ]

    operations = [
        migrations.RunPython(add_70_account, remove_70_account),
    ]
