"""
Сидер стандартных статей расходов/доходов для DEFAULT-org.

Группы:
    КОММУНАЛКА (parent: 26.01)
        - GAS / ELECTRICITY / WATER / HEAT
    СВЯЗЬ (parent: 26.02)
        - INTERNET / PHONE
    ПЕРСОНАЛ (parent: 70 / 26.03 / 91.02)
        - SALARY / PAYROLL_TAX
    ПРОИЗВОДСТВО (модульные, привязка к НЗП)
        - VET_SUPPLIES / DISINFECTION / FEED_PURCHASE
    ПРОЧЕЕ
        - OTHER_EXPENSE / OTHER_INCOME / OFFICE / ADVERTISING / TRANSPORT

Идемпотентно по (org, code).
"""
from django.db import migrations


# (code, name, kind, default_subaccount_code, default_module_code, parent_code)
ARTICLES = [
    # Коммуналка — детализация субсчёта 26.01
    ("UTILS",        "Коммунальные услуги (общее)",  "expense", "26.01", None, None),
    ("GAS",          "Газ",                          "expense", "26.01", None, "UTILS"),
    ("ELECTRICITY",  "Электроэнергия",               "expense", "26.01", None, "UTILS"),
    ("WATER",        "Водоснабжение",                "expense", "26.01", None, "UTILS"),
    ("HEAT",         "Отопление",                    "expense", "26.01", None, "UTILS"),
    ("WASTE",        "Вывоз мусора/ассенизация",     "expense", "26.01", None, "UTILS"),

    # Связь — детализация 26.02
    ("COMMS",        "Связь (общее)",                "expense", "26.02", None, None),
    ("INTERNET",     "Интернет",                     "expense", "26.02", None, "COMMS"),
    ("PHONE",        "Телефон / мобильная связь",    "expense", "26.02", None, "COMMS"),

    # Персонал
    ("SALARY",       "Зарплата",                     "salary",  "70.01", None, None),
    ("PAYROLL_TAX",  "Налоги/взносы с ФОТ",          "expense", "26.03", None, None),

    # Производственные (привязаны к НЗП через модули)
    ("VET_SUPPLIES",   "Ветеринарные препараты",     "expense", "10.03", "vet",      None),
    ("FEED_PURCHASE",  "Закуп ингредиентов корма",   "expense", "10.01", "feed",     None),
    ("DISINFECTION",   "Дезинфекция/санобработка",   "expense", "20.03", "incubation", None),
    ("EQUIP_REPAIR",   "Ремонт оборудования",        "expense", "26.09", None,       None),
    ("EQUIP_MAINT",    "Обслуживание оборудования",  "expense", "26.09", None,       None),

    # Транспорт/логистика
    ("FUEL",         "Топливо/ГСМ",                  "expense", "26.09", None, None),
    ("TRANSPORT",    "Транспортные услуги",          "expense", "44.02", None, None),

    # Офис / прочее
    ("OFFICE",       "Канцелярия и офис",            "expense", "26.03", None, None),
    ("ADVERTISING",  "Реклама и маркетинг",          "expense", "44.09", None, None),
    ("RENT",         "Аренда помещений",             "expense", "26.01", None, None),

    # Налоги (не ФОТ)
    ("TAX_OTHER",    "Налоги (прочие)",              "expense", "91.02", None, None),

    # Прочие расходы / доходы
    ("OTHER_EXPENSE", "Прочие расходы",              "expense", "91.02", None, None),
    ("OTHER_INCOME",  "Прочие доходы",               "income",  "91.01", None, None),
    ("FX_GAIN",       "Курсовые разницы (доход)",    "income",  "91.01", None, None),
    ("FX_LOSS",       "Курсовые разницы (расход)",   "expense", "91.02", None, None),
]


def seed_articles(apps, schema_editor):
    Organization = apps.get_model("organizations", "Organization")
    Module = apps.get_model("modules", "Module")
    GLSubaccount = apps.get_model("accounting", "GLSubaccount")
    ExpenseArticle = apps.get_model("accounting", "ExpenseArticle")

    try:
        org = Organization.objects.get(code="DEFAULT")
    except Organization.DoesNotExist:
        return

    # Подсчёты по коду в рамках org
    sub_by_code = {
        s.code: s
        for s in GLSubaccount.objects.filter(account__organization=org)
    }
    modules_by_code = {m.code: m for m in Module.objects.all()}

    # Двухпроходный сидинг: сначала без parent, потом обновим parent_id.
    parent_code_map: dict[str, str] = {}
    for code, name, kind, sub_code, mod_code, parent_code in ARTICLES:
        sub = sub_by_code.get(sub_code) if sub_code else None
        module = modules_by_code.get(mod_code) if mod_code else None
        ExpenseArticle.objects.update_or_create(
            organization=org,
            code=code,
            defaults={
                "name": name,
                "kind": kind,
                "default_subaccount": sub,
                "default_module": module,
                "is_active": True,
            },
        )
        if parent_code:
            parent_code_map[code] = parent_code

    # Второй проход — простановка parent.
    by_code = {a.code: a for a in ExpenseArticle.objects.filter(organization=org)}
    for child_code, parent_code in parent_code_map.items():
        child = by_code.get(child_code)
        parent = by_code.get(parent_code)
        if child and parent and child.parent_id != parent.id:
            child.parent = parent
            child.save(update_fields=["parent"])


def unseed_articles(apps, schema_editor):
    # Откат — не удаляем, чтобы не словить PROTECT по journal_entries.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("accounting", "0008_expensearticle_journalentry_expense_article_and_more"),
        ("payments", "0003_payment_expense_article"),
    ]

    operations = [
        migrations.RunPython(seed_articles, unseed_articles),
    ]
