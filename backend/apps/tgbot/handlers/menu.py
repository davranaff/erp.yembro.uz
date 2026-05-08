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

import logging

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb
from ..services.menu_scope import (
    can_see_section,
    is_owner,
    user_module_levels,
)

logger = logging.getLogger(__name__)


# Главное меню — плоское: все финансовые подразделы + 2 кнопки скачивания
# Excel. Раньше были «Moliya / Modullar / Hisobotlar», но Modullar и
# Hisobotlar были редко-используемыми навигационными слоями — оператор
# хотел сразу попасть в финансовые отчёты, поэтому свернули.
#
# Формат: (label, callback_data, [required_modules])
# Кнопка показывается если у юзера есть r-доступ ХОТЯ БЫ К ОДНОМУ модулю
# из списка. Owner видит всё.
_MAIN_BUTTONS: list[tuple[str, str, list[str]]] = [
    ("💵 Kassa/bank",            "fin:cash",        ["ledger", "reports"]),
    ("👥 Mijoz qarzi",           "fin:debt",        ["sales", "reports"]),
    ("🏢 Yetkazib beruvchi qarzi", "fin:cred",      ["purchases", "reports"]),
    ("📈 P&L",                   "fin:pnl:week",    ["reports", "ledger"]),
    ("💸 Sotuvlar",              "fin:sales:week",  ["sales", "reports"]),
    ("📦 Sklad qoldiqlari",      "fin:stock",       ["stock", "reports"]),
    ("📥 Mijoz qarzi (Excel)",   "dl:debtors",      ["sales", "reports"]),
    ("📥 Sklad qoldiqlari (Excel)", "dl:stock",     ["stock", "reports", "ledger"]),
]


def _menu_buttons_for(link) -> list[tuple[str, str]]:
    """Список кнопок главного меню после RBAC-фильтра.

    Если юзер не видит ничего — оставим /help чтобы было что нажать.
    """
    from ..services.menu_scope import has_any_access

    levels = user_module_levels(link)
    if is_owner(levels):
        return [(label, cb) for label, cb, _ in _MAIN_BUTTONS]
    buttons = [
        (label, cb) for (label, cb, mods) in _MAIN_BUTTONS
        if has_any_access(levels, mods)
    ]
    if not buttons:
        return [("ℹ️ Yordam", "home:help")]
    return buttons


def _menu_text(link) -> str:
    """Заголовок меню. Если owner — без подписи; иначе подпишем сколько
    из доступных кнопок видно — чтобы юзер понимал, почему мало."""
    from ..services.menu_scope import has_any_access

    levels = user_module_levels(link)
    if is_owner(levels):
        return "🏠 <b>Asosiy menyu</b>\n\nBo'limni tanlang:"
    visible_count = sum(
        1 for _, _, mods in _MAIN_BUTTONS if has_any_access(levels, mods)
    )
    if visible_count == 0:
        return (
            "🏠 <b>Asosiy menyu</b>\n\n"
            "Sizda hech qanday bo'limga ruxsat yo'q. Administrator bilan bog'laning."
        )
    return (
        f"🏠 <b>Asosiy menyu</b>\n"
        f"<i>{visible_count} ta bo'lim mavjud</i>\n\n"
        f"Bo'limni tanlang:"
    )


def _is_cp_link(link) -> bool:
    return bool(link and link.counterparty_id and not link.user_id)


@command("/menu", help="Asosiy menyu", audience="any", category="main")
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
    elif section in ("modules", "batch", "prod"):
        # batch / prod — legacy callbacks от старых сообщений с inline-кнопками,
        # переадресуем на новый единый «Modullar».
        from .modules_hub import render_modules_section
        render_modules_section(ctx)
    elif section == "reports":
        # Hisobotlar тоже разбито по модулям: выбираешь модуль → его аналитика.
        from .modules_hub import render_reports_modules
        render_reports_modules(ctx)
    elif section == "help":
        from .help_cmd import handle_help
        handle_help(ctx)
    else:
        # Логируем неизвестный section — поможет диагностировать stale-worker
        # сценарии (юзер кликнул home:newsection, но worker запущен с
        # version-N кода без этой ветки).
        logger.warning(
            "home callback: unknown section=%r (chat=%s) — most likely "
            "stale worker, restart with --force-recreate",
            section, ctx.chat_id,
        )
        send_message(
            ctx.chat_id,
            f"Bo'lim topilmadi: <code>{section}</code>",
            reply_markup=kb([("🏠 Bosh menyu", "home")], cols=1),
        )
