"""
Per-user/per-link RBAC-фильтрация TG-меню.

Цель: head feed-модуля видит ТОЛЬКО feed-кнопки (партии замеса, мешки,
рецепты), не видит финансы или vet. Owner организации (admin доступ к
admin-модулю) видит всё. Counterparty-линки получают полностью отдельное
меню (см. ``counterparty_menu``), без сотрудничьих разделов.

Подход:
1. ``user_module_levels(link)`` — один SQL-запрос, возвращает {module_code: level}
   для активной membership. Override > Role.
2. ``can_see(levels, "fin")`` — проверка какой раздел показывать на корне.
3. ``filter_buttons(buttons, levels)`` — keep только те, у которых scope доступен.

Используется и handlers/menu.py (фильтр inline-кнопок), и /start handler
(setMyCommands per chat — чтобы / меню Telegram тоже было персональным).
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable


# ─── Раздел корневого меню → требования ───────────────────────────────────
# Юзер видит раздел если у него есть >=r НА ХОТЯ БЫ ОДИН модуль из списка.
# Owner (admin модуля 'admin') видит всё бесконтрольно.
SECTION_MODULES: dict[str, list[str]] = {
    "fin":     ["sales", "purchases", "payments", "ledger"],
    "modules": [
        "matochnik", "incubation", "feedlot", "slaughter",
        "feed", "vet", "stock",
    ],
    "reports": [
        "reports", "ledger", "sales", "purchases",
        "matochnik", "incubation", "feedlot", "slaughter", "feed", "vet",
    ],
    # Legacy ключи на случай если в callback всё ещё пришёл home:batch / home:prod —
    # переадресуем на modules.
    "batch":   [
        "matochnik", "incubation", "feedlot", "slaughter",
        "feed", "vet", "stock",
    ],
    "prod":    [
        "matochnik", "incubation", "feedlot", "slaughter",
        "feed", "vet", "stock",
    ],
}


# ─── Команды бота → required module ──────────────────────────────────────
# (для setMyCommands per chat — Telegram сам спрячет недоступные команды).
COMMAND_MODULES: dict[str, str] = {
    "menu":     "",            # всегда доступно
    "help":     "",
    "org":      "",            # переключение org доступно всем
    "feedlot":  "feedlot",
    "batch":    "feedlot",
    "herd":     "matochnik",
    "sales":    "reports",
    "pnl":      "reports",
    "cash":     "ledger",
    "debt":     "sales",       # дебиторка — раздел продаж
    "cred":     "purchases",   # кредиторка — раздел закупок
    "production": "",          # сводка — пустяк
}


def user_module_levels(link) -> dict[str, str]:
    """{module_code: AccessLevel} для активной membership за один SQL.

    Учитывает: ``link.active_organization`` (если юзер /org переключал),
    иначе ``link.organization``. Если членства нет — пустой dict.

    Override побеждает role-permission. Если на модуль есть и override,
    и роль — берём override. Если несколько ролей — берём максимум.
    """
    from apps.common.permissions import _LEVEL_ORDER
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import AccessLevel, RolePermission, UserModuleAccessOverride

    if link is None or not link.user_id:
        return {}

    org = getattr(link, "active_organization", None) or link.organization
    membership = OrganizationMembership.objects.filter(
        organization=org, user_id=link.user_id, is_active=True,
    ).first()
    if membership is None:
        return {}

    # Override — финальный для каждого модуля
    overrides = dict(
        UserModuleAccessOverride.objects.filter(
            membership=membership,
        ).values_list("module__code", "level")
    )

    # Роли — собираем максимум
    role_levels: dict[str, list[str]] = defaultdict(list)
    rp_qs = RolePermission.objects.filter(
        role__assignments__membership=membership,
    ).values_list("module__code", "level")
    for code, level in rp_qs:
        role_levels[code].append(level)

    result: dict[str, str] = {}
    all_codes = set(overrides) | set(role_levels)
    for code in all_codes:
        if code in overrides:
            result[code] = overrides[code]
        else:
            levels = role_levels[code]
            result[code] = max(levels, key=lambda lv: _LEVEL_ORDER.get(lv, 0)) \
                if levels else AccessLevel.NONE
    return result


def is_owner(levels: dict[str, str]) -> bool:
    """Owner = admin доступ к 'admin'-модулю. Видит всё во всех разделах."""
    from apps.rbac.models import AccessLevel
    return levels.get("admin") == AccessLevel.ADMIN


def has_any_access(levels: dict[str, str], modules: Iterable[str]) -> bool:
    """True если у юзера >=r на ХОТЯ БЫ ОДИН модуль из списка."""
    from apps.common.permissions import level_satisfies
    return any(level_satisfies(levels.get(m, "none"), "r") for m in modules)


def can_see_section(levels: dict[str, str], section: str) -> bool:
    if is_owner(levels):
        return True
    modules = SECTION_MODULES.get(section, [])
    if not modules:
        return True  # неизвестный раздел — пускаем (избегаем false-negatives)
    return has_any_access(levels, modules)


def commands_for_user(levels: dict[str, str]) -> list[dict]:
    """Список команд для setMyCommands per chat — только доступные.

    Owner получает все. Каждой команде сопоставлен required-модуль (см.
    COMMAND_MODULES); если у юзера на этот модуль нет r — команда не
    показывается в /menu Telegram'а.
    """
    from apps.common.permissions import level_satisfies

    available: list[dict] = []
    descriptions = {
        "menu":       "Asosiy menyu",
        "help":       "Yordam",
        "org":        "Tashkilotni tanlash",
        "feedlot":    "Bo'rdoqi partiyalari",
        "batch":      "Partiya kartasi",
        "herd":       "Onalik podasi",
        "sales":      "Davr sotuvlari",
        "pnl":        "Daromad/zarar",
        "cash":       "Kassa va bank",
        "debt":       "Mijoz qarzlari",
        "cred":       "Yetkazib beruvchi qarzlari",
        "production": "Ishlab chiqarish hozir",
    }
    owner = is_owner(levels)
    for cmd, mod in COMMAND_MODULES.items():
        if mod == "" or owner or level_satisfies(levels.get(mod, "none"), "r"):
            available.append({
                "command": cmd,
                "description": descriptions.get(cmd, cmd),
            })
    return available


# ─── Counterparty (client) menu commands ──────────────────────────────────


def commands_for_counterparty() -> list[dict]:
    """Команды для клиент-линка: только клиентские. На узбекском."""
    return [
        {"command": "menu", "description": "Asosiy menyu"},
        {"command": "buyurtmalar", "description": "Mening buyurtmalarim"},
        {"command": "qarz", "description": "Qarzdorligim"},
        {"command": "holat", "description": "Bloklash holati"},
        {"command": "help", "description": "Yordam"},
    ]
