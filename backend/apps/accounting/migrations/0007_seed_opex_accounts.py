"""
Досеять счета для "прочих" операций (OpEx) и модулей feed/vet.

Добавляем:
    - 20.05 Корма — НЗП (модуль feed)
    - 20.06 Вет. аптека — НЗП (модуль vet)
    - 26.XX Общехозяйственные расходы
    - 44.XX Коммерческие расходы
    - 91.XX Прочие доходы и расходы

Это базовый набор. Пользователь сможет создавать свои субсчёта через
UI (после расширения GLSubaccountViewSet на CRUD).
"""
from django.db import migrations


NEW_ACCOUNTS = [
    # (code, name, type)
    ("26", "Общехозяйственные расходы", "expense"),
    ("44", "Коммерческие расходы",      "expense"),
    ("91", "Прочие доходы и расходы",   "expense"),
]

NEW_SUBACCOUNTS = [
    # (parent_code, sub_code, sub_name, module_code_or_None)
    # НЗП для модулей feed/vet
    ("20", "20.05", "Корма — НЗП",             "feed"),
    ("20", "20.06", "Вет. аптека — НЗП",       "vet"),
    # Общехоз.
    ("26", "26.01", "Аренда и коммуналка",     None),
    ("26", "26.02", "Связь и интернет",        None),
    ("26", "26.03", "Канцелярия",              None),
    ("26", "26.09", "Прочие общехоз.",         None),
    # Коммерческие
    ("44", "44.01", "Упаковка",                None),
    ("44", "44.02", "Доставка клиентам",       None),
    ("44", "44.09", "Прочие коммерческие",     None),
    # Прочие доходы/расходы
    ("91", "91.01", "Прочие доходы",           None),
    ("91", "91.02", "Прочие расходы",          None),
]


def seed_opex(apps, schema_editor):
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
        ("accounting", "0006_seed_sales_accounts"),
    ]

    operations = [
        migrations.RunPython(seed_opex, migrations.RunPython.noop),
    ]
