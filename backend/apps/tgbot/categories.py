"""
Реестр категорий команд бота.

Каждая команда (декоратор `@command`) получает поле `category`. Если не
задано явно — резолвится автоматически через `MODULE_TO_CATEGORY` по полю
`module` команды.

Зачем: `/help` и `/menu` группируют команды по категориям, не по эвристикам.
Добавление нового модуля — одна запись в `MODULE_TO_CATEGORY` (или явный
`category=` в `@command`).

Контракт:
  - `_CATEGORY_DEFS`: список (code, label, sort_order). Порядок sort_order
    задаёт порядок групп в /help.
  - `MODULE_TO_CATEGORY`: ERP-module-code → category-code.
  - Неизвестные категории попадают в "misc" (последняя группа).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDef:
    code: str
    label: str  # с emoji, готовое для печати
    sort_order: int


_CATEGORY_DEFS: list[CategoryDef] = [
    CategoryDef("main",       "🏠 Главное",         0),
    CategoryDef("stock",      "📦 Склад",          10),
    CategoryDef("production", "🥣 Производство",   20),
    CategoryDef("sales",      "💰 Продажи",         30),
    CategoryDef("payments",   "💵 Касса / банк",   40),
    CategoryDef("finance",    "📊 Финансы",         50),
    CategoryDef("reports",    "📅 Сводки",          60),
    CategoryDef("org",        "🏢 Организация",    70),
    CategoryDef("admin",      "🔧 Админ",           80),
    CategoryDef("client",     "👤 Клиент",          90),
    CategoryDef("misc",       "⚙️ Прочее",         100),
]

CATEGORIES: dict[str, CategoryDef] = {c.code: c for c in _CATEGORY_DEFS}


# ERP-модуль → категория. Нет в маппинге → "misc".
MODULE_TO_CATEGORY: dict[str, str] = {
    "purchases": "stock",
    "stock":     "stock",

    "feed":       "production",
    "matochnik":  "production",
    "incubation": "production",
    "feedlot":    "production",
    "slaughter":  "production",
    "vet":        "production",

    "sales":    "sales",
    "payments": "payments",
    "ledger":   "finance",
    "reports":  "reports",

    "core":  "misc",
    "admin": "admin",
}


def resolve_category(*, explicit: str | None, module: str | None, audience: str = "admin") -> str:
    """
    Резолв category для команды:
        1) Явный @command(category="...") побеждает.
        2) audience=counterparty → "client" (кабинет клиента).
        3) module → MODULE_TO_CATEGORY[module].
        4) fallback → "misc".
    """
    if explicit:
        return explicit if explicit in CATEGORIES else "misc"
    if audience == "counterparty":
        return "client"
    if module and module in MODULE_TO_CATEGORY:
        return MODULE_TO_CATEGORY[module]
    return "misc"


def sorted_categories() -> list[CategoryDef]:
    return sorted(_CATEGORY_DEFS, key=lambda c: c.sort_order)
