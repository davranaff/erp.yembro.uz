"""
/menu — главное inline-меню с RBAC-фильтрацией.

Кнопки автоматически прячутся если у юзера нет доступа к разделу.
Owner (admin модуль 'admin') видит всё. Head feed-модуля видит только
батчи/производство, без финансов и т.д.

Внутри каждого раздела используются inline-кнопки (callback_query) —
юзер не должен набирать команды через /, всё клики. Рядом с любым
сообщением где есть данные — есть «← Назад» / «🏠 Меню».
"""
from __future__ import annotations

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb
from ..services.menu_scope import (
    can_see_section,
    is_owner,
    user_module_levels,
)


# Каждый кортеж: (label, callback_data, section_key для RBAC).
# Section_key пустой = доступно всем без ограничений.
_ALL_SECTIONS = [
    ("💰 Moliya",        "home:fin",     "fin"),
    ("📦 Partiyalar",    "home:batch",   "batch"),
    ("🐔 Ishlab chiqarish", "home:prod", "prod"),
    ("📊 Hisobotlar",    "home:reports", "reports"),
]


def _menu_buttons_for(link) -> list[tuple[str, str]]:
    """Только кнопки разделов, к которым у юзера есть доступ.

    Если юзер не видит ничего (странно — но возможно если убрали все
    permissions) — оставим хотя бы /help чтобы было что нажать.
    """
    levels = user_module_levels(link)
    buttons = [
        (label, cb) for (label, cb, section) in _ALL_SECTIONS
        if can_see_section(levels, section)
    ]
    if not buttons:
        return [("ℹ️ Yordam", "home:help")]
    return buttons


def _menu_text(link) -> str:
    """Заголовок меню. Если owner — без подписи; иначе подпишем «scope: …»
    чтобы юзер понимал, почему кнопок мало."""
    levels = user_module_levels(link)
    if is_owner(levels):
        return "🏠 <b>Asosiy menyu</b>\n\nBo'limni tanlang:"
    visible = [
        label for label, _, section in _ALL_SECTIONS
        if can_see_section(levels, section)
    ]
    if not visible:
        return (
            "🏠 <b>Asosiy menyu</b>\n\n"
            "Sizda hech qanday modulga ruxsat yo'q. Administrator bilan bog'laning."
        )
    scope_hint = ", ".join(s for s in visible)
    return (
        f"🏠 <b>Asosiy menyu</b>\n"
        f"<i>Sizning ruxsatingiz: {scope_hint}</i>\n\n"
        f"Bo'limni tanlang:"
    )


def _is_cp_link(link) -> bool:
    return bool(link and link.counterparty_id and not link.user_id)


@command("/menu", help="Asosiy menyu", audience="any")
def handle_menu_cmd(ctx: HandlerCtx) -> None:
    if _is_cp_link(ctx.link):
        from .counterparty import render_counterparty_menu
        render_counterparty_menu(ctx)
        return
    send_message(
        ctx.chat_id,
        _menu_text(ctx.link),
        reply_markup=kb(_menu_buttons_for(ctx.link), cols=2),
    )


@on_callback("home")
def handle_home_callback(ctx: HandlerCtx) -> None:
    """`home` — корень; `home:<section>` — раздел."""
    section = ctx.args[0] if ctx.args else ""

    if _is_cp_link(ctx.link):
        # Клиент-кабинет — completely separate menu tree.
        from .counterparty import render_counterparty_menu
        render_counterparty_menu(ctx)
        return

    if not section:
        # Корень
        text = _menu_text(ctx.link)
        markup = kb(_menu_buttons_for(ctx.link), cols=2)
        if ctx.message_id:
            edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
        else:
            send_message(ctx.chat_id, text, reply_markup=markup)
        return

    # RBAC-gate для подменю
    levels = user_module_levels(ctx.link)
    if not can_see_section(levels, section):
        send_message(
            ctx.chat_id,
            "⛔ Bu bo'limga sizda ruxsat yo'q.",
            reply_markup=kb([("← Orqaga", "home")], cols=1),
        )
        return

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
    elif section == "help":
        from .help_cmd import handle_help
        handle_help(ctx)
    else:
        send_message(ctx.chat_id, "Bo'lim topilmadi.")
