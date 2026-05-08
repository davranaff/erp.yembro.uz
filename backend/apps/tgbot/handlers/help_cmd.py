"""
/help — список команд, доступных текущему юзеру.

Группы определяются по `CommandSpec.category` (см. apps.tgbot.categories).
Сортировка групп — `sort_order`, внутри группы — по имени команды.

Фильтр:
  - private=True не показываем (легаси: /report /balance ...)
  - команда требует module RBAC, у юзера нет — скрываем
  - audience=admin — только для admin-link, audience=counterparty — для
    cp-link, "any" — для обоих

Чтобы добавить новую группу — одна запись в apps.tgbot.categories._CATEGORY_DEFS.
Чтобы добавить команду — `@command(name, module=..., category="...")`.
"""
from __future__ import annotations

from ..bot import send_message
from ..categories import CATEGORIES, sorted_categories
from ..dispatcher import COMMANDS, HandlerCtx, command


@command("/help", help="Список команд", audience="any", category="main")
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
        cat = getattr(spec, "category", "misc")
        if cat not in CATEGORIES:
            cat = "misc"
        line = f"{spec.name} — {spec.help_line}" if spec.help_line else spec.name
        grouped.setdefault(cat, []).append(line)

    if not grouped:
        return "🤖 <b>Yembro ERP Bot</b>\n\n(нет доступных команд)"

    parts: list[str] = ["🤖 <b>Yembro ERP Bot</b>\n"]
    org = getattr(link, "active_organization", None) or getattr(link, "organization", None)
    if org and not is_counterparty:
        parts.append(f"<i>Организация: {org.name}</i>\n")

    for cat_def in sorted_categories():
        if cat_def.code not in grouped:
            continue
        parts.append(f"<b>{cat_def.label}</b>")
        for line in grouped[cat_def.code]:
            parts.append(f"  {line}")
        parts.append("")  # blank line между группами

    parts.append("💡 /menu — inline-навигация")
    parts.append("💡 /bekor — отмена wizard'а")
    return "\n".join(parts)
