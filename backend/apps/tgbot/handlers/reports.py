"""
Раздел /reports в inline-меню. Показывает строки P&L по модулям за месяц.
Drill-down на конкретный модуль не делаем в MVP — для деталей пусть юзер
дёрнет /pnl month и читает там разбивку.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, has_module_access
from ..keyboards import kb_back


def _fmt_uzs(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


def _fmt_signed(value) -> str:
    if value is None or value == "":
        return "0"
    n = Decimal(str(value))
    if n == 0:
        return "0"
    sign = "+" if n > 0 else "−"
    return f"{sign}{_fmt_uzs(abs(n))}"


def render_reports_section(ctx: HandlerCtx) -> None:
    if not has_module_access(ctx.link, "reports"):
        send_message(ctx.chat_id, "Нет доступа к модулю <b>Отчёты</b>.")
        return

    from apps.accounting.services.reports import compute_pl_by_module

    org = ctx.org()
    today = date.today()
    df = today.replace(day=1)
    result = compute_pl_by_module(org, date_from=df, date_to=today)

    lines = [
        "📊 <b>P&amp;L по модулям</b>",
        f"<i>{df.isoformat()} — {today.isoformat()}</i>",
        "",
    ]
    if not result.rows:
        lines.append("Нет данных за период.")
    else:
        for r in result.rows[:8]:
            lines.append(
                f"<b>{r.module_name}</b>\n"
                f"  доход   <code>{_fmt_uzs(r.revenue)}</code>\n"
                f"  расход  <code>{_fmt_uzs(r.expense)}</code>\n"
                f"  прибыль <code>{_fmt_signed(r.profit)}</code>"
            )
        lines.append("")
        lines.append(
            f"<b>Итого прибыль:</b> <code>{_fmt_signed(result.total_profit)}</code> сум"
        )

    text = "\n".join(lines)
    markup = kb_back("home")
    if ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)
