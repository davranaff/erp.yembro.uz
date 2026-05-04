from django.db import migrations


ACCOUNTS = [
    # (code, name, type)
    ("10", "Материалы", "asset"),
    ("20", "Основное производство", "expense"),
    ("43", "Готовая продукция", "asset"),
    ("50", "Касса", "asset"),
    ("51", "Расчётный счёт", "asset"),
    ("60", "Расчёты с поставщиками", "liability"),
    ("62", "Расчёты с покупателями", "asset"),
    ("70", "Расчёты с персоналом", "liability"),
    ("79", "Внутрихозяйственные расчёты", "service"),
]

# (parent_code, sub_code, sub_name, module_code_or_None)
SUBACCOUNTS = [
    ("10", "10.01", "Сырьё и материалы", None),
    ("10", "10.02", "Живая птица", None),
    ("10", "10.03", "Ветпрепараты", "vet"),
    ("10", "10.05", "Корма", "feed"),
    ("20", "20.01", "Маточник", "matochnik"),
    ("20", "20.02", "Фабрика откорма", "feedlot"),
    ("20", "20.03", "Инкубация", "incubation"),
    ("20", "20.04", "Убойня", "slaughter"),
    ("43", "43.01", "Тушки и разделка", "slaughter"),
    ("43", "43.02", "Инкубационное яйцо", "matochnik"),
    ("43", "43.03", "Живая птица на продажу", "feedlot"),
    ("50", "50.01", "Касса UZS", None),
    ("51", "51.01", "Расчётный счёт UZS", None),
    ("60", "60.01", "Поставщики UZS", None),
    ("60", "60.02", "Поставщики в валюте", None),
    ("62", "62.01", "Покупатели UZS", None),
    ("79", "79.01", "Межмодульные передачи", None),
]


def seed_chart(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    GLAccount = apps.get_model("accounting", "GLAccount")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        # ничего не делаем если Default Org ещё нет (пустая dev-среда — создаст rbac/0003)
        return

    modules_by_code = {m.code: m for m in Module.objects.all()}

    code_to_account = {}
    for code, name, type_ in ACCOUNTS:
        acc, _ = GLAccount.objects.update_or_create(
            organization=org,
            code=code,
            defaults={"name": name, "type": type_},
        )
        code_to_account[code] = acc

    for parent_code, sub_code, sub_name, mod_code in SUBACCOUNTS:
        parent = code_to_account[parent_code]
        module = modules_by_code.get(mod_code) if mod_code else None
        GLSubaccount.objects.update_or_create(
            account=parent,
            code=sub_code,
            defaults={"name": sub_name, "module": module},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0004_journalentry_batch_and_more"),
        ("rbac", "0003_seed_default_org_and_roles"),
        ("modules", "0003_seed_modules"),
    ]

    operations = [
        migrations.RunPython(seed_chart, migrations.RunPython.noop),
    ]
