"""
/help — авто-генерируется из реестра COMMANDS.

Скрытые команды (`private=True`, например legacy `/report /balance ...`) не
попадают в /help — пользователю предлагаем `/menu` для inline-навигации.
"""
from __future__ import annotations

from ..bot import send_message
from ..dispatcher import COMMANDS, HandlerCtx, command


@command("/help", help="Список команд")
def handle_help(ctx: HandlerCtx) -> None:
    send_message(ctx.chat_id, _build_help_text(ctx.link))


def _build_help_text(link) -> str:
    """Собирает help-текст по командам, доступным юзеру (private скрыты,
    модули, к которым нет RBAC — тоже скрыты)."""
    from ..dispatcher import has_module_access

    seen_handlers: set[int] = set()
    lines: list[str] = []
    # Сортировка: по имени команды, для стабильности.
    for spec in sorted(COMMANDS.values(), key=lambda s: s.name):
        if spec.private:
            continue
        # Дедуп — одна функция могла быть зарегистрирована под несколькими
        # именами (alias). Берём первое имя в алфавитном порядке.
        handler_key = id(spec.handler)
        if handler_key in seen_handlers:
            continue
        if spec.module and not has_module_access(link, spec.module):
            continue
        seen_handlers.add(handler_key)
        lines.append(f"{spec.name} — {spec.help_line}" if spec.help_line else spec.name)

    body = "\n".join(lines) if lines else "(нет доступных команд)"
    return (
        "🤖 <b>Yembro ERP Bot</b>\n\n"
        "Доступные команды:\n"
        f"{body}\n\n"
        "💡 Откройте /menu для удобной навигации."
    )
