"""
/help — список команд, доступных текущему юзеру.

Фильтр:
  - private=True не показываем (легаси: /report /balance ...)
  - команда требует module RBAC, у юзера нет — скрываем
  - audience=admin — только для admin-link, audience=counterparty — для
    cp-link, "any" — для обоих

Группировка:
  Команды группируются по категориям (Склад / Производство / Финансы /
  Сводки / Прочее) — определяется по module-коду либо по эвристике имён.
  Так длинный плоский список превращается в навигируемый блок.
"""
from __future__ import annotations

from ..bot import send_message
from ..dispatcher import COMMANDS, HandlerCtx, command


# Категория → emoji + порядок отображения
_CATEGORY_ORDER: list[tuple[str, str]] = [
    ("main",       "🏠 <b>Главное</b>"),
    ("stock",      "📦 <b>Склад</b>"),
    ("production", "🥣 <b>Производство</b>"),
    ("finance",    "💰 <b>Финансы</b>"),
    ("digest",     "📅 <b>Сводки</b>"),
    ("org",        "🏢 <b>Организация</b>"),
    ("client",     "👤 <b>Клиентский кабинет</b>"),
    ("misc",       "🔧 <b>Прочее</b>"),
]


def _categorize(spec) -> str:
    """Маппит CommandSpec → категория. Эвристика по module + имени."""
    name = spec.name
    audience = getattr(spec, "audience", "admin")
    module = spec.module

    if audience == "counterparty":
        return "client"
    if name in ("/help", "/menu", "/start", "/bekor"):
        return "main"
    if name in ("/digest", "/digest_on", "/digest_off"):
        return "digest"
    if name == "/org":
        return "org"
    if module == "purchases" or module == "stock" or name in ("/qabul", "/chiqim", "/qoldiq"):
        return "stock"
    if module == "feed" or name == "/aralash":
        return "production"
    if module == "reports" or name in ("/cash", "/pnl", "/sales", "/debt"):
        return "finance"
    return "misc"


@command("/help", help="Список команд", audience="any")
def handle_help(ctx: HandlerCtx) -> None:
    send_message(ctx.chat_id, _build_help_text(ctx.link))


def _build_help_text(link) -> str:
    from ..dispatcher import has_module_access

    is_counterparty = getattr(link, "user_id", None) is None
    seen_handlers: set[int] = set()
    grouped: dict[str, list[str]] = {}

    for spec in sorted(COMMANDS.values(), key=lambda s: s.name):
        if spec.private:
            continue
        handler_key = id(spec.handler)
        if handler_key in seen_handlers:
            continue
        # Audience-gate
        audience = getattr(spec, "audience", "admin")
        if audience == "admin" and is_counterparty:
            continue
        if audience == "counterparty" and not is_counterparty:
            continue
        # RBAC-gate (для admin-link)
        if not is_counterparty and spec.module and not has_module_access(link, spec.module):
            continue
        seen_handlers.add(handler_key)
        cat = _categorize(spec)
        line = f"{spec.name} — {spec.help_line}" if spec.help_line else spec.name
        grouped.setdefault(cat, []).append(line)

    if not grouped:
        return "🤖 <b>Yembro ERP Bot</b>\n\n(нет доступных команд)"

    parts: list[str] = ["🤖 <b>Yembro ERP Bot</b>\n"]
    org = getattr(link, "active_organization", None) or getattr(link, "organization", None)
    if org and not is_counterparty:
        parts.append(f"<i>Организация: {org.name}</i>\n")
    for cat, header in _CATEGORY_ORDER:
        if cat not in grouped:
            continue
        parts.append(header)
        for line in grouped[cat]:
            parts.append(f"  {line}")
        parts.append("")  # пустая строка между группами
    parts.append("💡 /menu — inline-навигация по разделам")
    parts.append("💡 /bekor — отменить активный wizard")
    return "\n".join(parts)
