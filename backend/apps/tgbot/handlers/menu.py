"""
/menu — главное inline-меню владельца.

Структура:
  💰 Финансы (home:fin)         📦 Партии (home:batch)
  🐔 Производство (home:prod)   📊 Отчёты (home:reports)
"""
from __future__ import annotations

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb


_MENU_TEXT = (
    "🏠 <b>Главное меню</b>\n\n"
    "Выберите раздел:"
)

_MENU_BUTTONS = [
    ("💰 Финансы", "home:fin"),
    ("📦 Партии", "home:batch"),
    ("🐔 Производство", "home:prod"),
    ("📊 Отчёты", "home:reports"),
]


@command("/menu", help="Главное меню")
def handle_menu_cmd(ctx: HandlerCtx) -> None:
    send_message(ctx.chat_id, _MENU_TEXT, reply_markup=kb(_MENU_BUTTONS, cols=2))


@on_callback("home")
def handle_home_callback(ctx: HandlerCtx) -> None:
    """Универсальный handler `home` (вернуться в главное меню) и `home:<section>`."""
    if ctx.callback_data in (None, "home"):
        # Возврат на главную — редактируем существующее сообщение.
        if ctx.message_id:
            edit_message_text(
                ctx.chat_id, ctx.message_id, _MENU_TEXT,
                reply_markup=kb(_MENU_BUTTONS, cols=2),
            )
        else:
            send_message(ctx.chat_id, _MENU_TEXT, reply_markup=kb(_MENU_BUTTONS, cols=2))
        return

    section = ctx.args[0] if ctx.args else ""
    if section == "fin":
        from .finance import render_finance_menu
        render_finance_menu(ctx)
    elif section == "batch":
        from .production import render_batches_section
        render_batches_section(ctx)
    elif section == "prod":
        from .production import render_production_section
        render_production_section(ctx)
    elif section == "reports":
        from .reports import render_reports_section
        render_reports_section(ctx)
    else:
        send_message(ctx.chat_id, "Раздел не найден.")
