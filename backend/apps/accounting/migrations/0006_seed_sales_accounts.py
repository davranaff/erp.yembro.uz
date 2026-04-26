"""
Доcеять субсчета для продаж:
    - 62.02 Покупатели в валюте
    - 90    Продажи (счёт)
    - 90.01 Выручка от продаж
    - 90.02 Себестоимость продаж
"""
from django.db import migrations


NEW_ACCOUNTS = [
    # (code, name, type)
    ("90", "Продажи", "income"),
]

NEW_SUBACCOUNTS = [
    # (parent_code, sub_code, sub_name, module_code_or_None)
    ("62", "62.02", "Покупатели в валюте", None),
    ("90", "90.01", "Выручка от продаж", None),
    ("90", "90.02", "Себестоимость продаж", None),
]


def seed_sales_accounts(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    modules_by_code = {m.code: m for m in Module.objects.all()}

    code_to_account = {a.code: a for a in GLAccount.objects.filter(organization=org)}
    for code, name, type_ in NEW_ACCOUNTS:
        acc, _ = GLAccount.objects.update_or_create(
            organization=org, code=code,
            defaults={"name": name, "type": type_},
        )
        code_to_account[code] = acc

    for parent_code, sub_code, sub_name, mod_code in NEW_SUBACCOUNTS:
        parent = code_to_account.get(parent_code)
        if parent is None:
            continue
        module = modules_by_code.get(mod_code) if mod_code else None
        GLSubaccount.objects.update_or_create(
            account=parent,
            code=sub_code,
            defaults={"name": sub_name, "module": module},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0005_seed_chart_of_accounts"),
    ]

    operations = [
        migrations.RunPython(seed_sales_accounts, migrations.RunPython.noop),
    ]
