"""
Добавляет субсчёт 71.01 «Расчёты с подотчётными лицами» в план счетов
DEFAULT-организации. Используется при закрытии CashAdvance: Дт расходная
статья / Кт 71.01 на сумму отчёта.
"""
from django.db import migrations


def add_71_account(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    parent, _ = GLAccount.objects.update_or_create(
        organization=org,
        code="71",
        defaults={"name": "Расчёты с подотчётными лицами", "type": "asset"},
    )
    GLSubaccount.objects.update_or_create(
        account=parent,
        code="71.01",
        defaults={"name": "Расчёты с подотчётными лицами (UZS)"},
    )


def remove_71_account(apps, schema_editor):
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    GLSubaccount.objects.filter(code="71.01").delete()
    GLAccount.objects.filter(code="71").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0010_cash_advance"),
    ]

    operations = [
        migrations.RunPython(add_71_account, remove_71_account),
    ]
