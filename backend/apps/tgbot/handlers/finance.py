"""
Финансовая секция бота: касса, дебиторка, кредиторка, P&L.

Главный приём: переиспользуем существующие сервисы
  - apps.dashboard.services.cash_balances / cashflow_chart
  - apps.accounting.services.reports.compute_pl_report / compute_pl_by_module
вместо того чтобы дублировать SQL.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import F

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback, has_module_access
from ..keyboards import kb, kb_back, kb_periods

logger = logging.getLogger(__name__)


# ─── helpers ─────────────────────────────────────────────────────────────


def _fmt_uzs(value) -> str:
    """100_000_000 → '100 000 000'. Принимает Decimal/str/None."""
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


def _ascii_sparkline(values: list[Decimal]) -> str:
    """`▁▂▃▅▇` сжимает значения по min/max в 5 уровней. Пусто → пустая строка."""
    if not values:
        return ""
    levels = "▁▂▃▄▅▆▇█"
    floats = [float(v) for v in values]
    lo, hi = min(floats), max(floats)
    span = hi - lo or 1
    return "".join(
        levels[min(len(levels) - 1, int((v - lo) / span * (len(levels) - 1)))]
        for v in floats
    )


def _period_range(period: str) -> tuple[date, date]:
    today = date.today()
    if period == "today":
        return today, today
    if period == "month":
        return today.replace(day=1), today
    # default week
    return today - timedelta(days=6), today


def _check_or_deny(ctx: HandlerCtx) -> bool:
    """Проверка ledger / reports доступа. Возвращает True если ok."""
    if has_module_access(ctx.link, "reports"):
        return True
    send_message(ctx.chat_id, "⛔ Нет доступа к модулю <b>Отчёты</b>.")
    return False


# ─── menu (callback `home:fin` / from /menu) ────────────────────────────


_FIN_MENU_TEXT = "💰 <b>Финансы</b>\n\nВыберите раздел:"
_FIN_MENU_BUTTONS = [
    ("💵 Касса/банк", "fin:cash"),
    ("📥 Дебиторка", "fin:debt"),
    ("📤 Кредиторка", "fin:cred"),
    ("📈 P&L", "fin:pnl:week"),
]


def render_finance_menu(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx):
        return
    markup = kb(_FIN_MENU_BUTTONS + [("← Назад", "home")], cols=2)
    if ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, _FIN_MENU_TEXT, reply_markup=markup)
    else:
        send_message(ctx.chat_id, _FIN_MENU_TEXT, reply_markup=markup)


# ─── /cash ───────────────────────────────────────────────────────────────


@command("/cash", help="Остатки кассы и банка + кэш-флоу 7 дн", module="reports")
def handle_cash_cmd(ctx: HandlerCtx) -> None:
    _render_cash(ctx)


@on_callback("fin:cash")
def handle_cash_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx):
        return
    _render_cash(ctx, edit=True)


def _render_cash(ctx: HandlerCtx, *, edit: bool = False) -> None:
    from apps.dashboard.services import cash_balances, cashflow_chart

    org = ctx.org()
    cash = cash_balances(org)
    points = cashflow_chart(org, days=7)

    lines = ["💵 <b>Касса и банк</b>", ""]
    for ch_key, ch_data in cash.items():
        if ch_key.startswith("_"):
            continue
        lines.append(
            f"  {ch_data['label']}: <code>{_fmt_uzs(ch_data['balance_uzs'])}</code> сум"
        )
    lines.append("")
    lines.append(f"💰 <b>Итого:</b> <code>{_fmt_uzs(cash['_total_uzs'])}</code> сум")

    if points:
        net_values = [Decimal(p["in_uzs"]) - Decimal(p["out_uzs"]) for p in points]
        spark = _ascii_sparkline(net_values)
        net_total = sum(net_values, Decimal("0"))
        lines.append("")
        lines.append("📊 <b>Чистый поток за 7 дн:</b>")
        lines.append(f"<code>{spark}</code>")
        lines.append(f"  итого: <code>{_fmt_uzs(net_total)}</code> сум")

    text = "\n".join(lines)
    markup = kb_back("home:fin")
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /debt ───────────────────────────────────────────────────────────────


@command("/debt", help="Топ-5 должников", module="reports")
def handle_debt_cmd(ctx: HandlerCtx) -> None:
    _render_debt(ctx)


@on_callback("fin:debt")
def handle_debt_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx):
        return
    _render_debt(ctx, edit=True)


def _render_debt(ctx: HandlerCtx, *, edit: bool = False) -> None:
    from apps.sales.models import SaleOrder

    org = ctx.org()
    today = date.today()
    debts = list(
        SaleOrder.objects
        .filter(
            organization=org,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .annotate(remaining=F("amount_uzs") - F("paid_amount_uzs"))
        .filter(remaining__gt=0)
        .select_related("customer")
        .order_by("-remaining")[:5]
    )

    lines = ["📥 <b>Дебиторка — топ-5</b>", ""]
    if not debts:
        lines.append("✅ Все продажи оплачены.")
    else:
        total = Decimal("0")
        for so in debts:
            overdue = ""
            if so.due_date and so.due_date < today:
                overdue = f" · ⚠️ просрочка {(today - so.due_date).days} дн"
            customer = so.customer.name if so.customer_id else "—"
            lines.append(
                f"• <b>{customer}</b>{overdue}\n"
                f"  <code>{so.doc_number}</code> · "
                f"<code>{_fmt_uzs(so.remaining)}</code> сум"
            )
            total += so.remaining
        lines.append("")
        lines.append(f"💼 <b>Итого по топ-5:</b> <code>{_fmt_uzs(total)}</code> сум")

    text = "\n".join(lines)
    markup = kb_back("home:fin")
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /cred (топ-5 кредиторов) ────────────────────────────────────────────


@on_callback("fin:cred")
def handle_cred_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx):
        return
    _render_cred(ctx, edit=True)


def _render_cred(ctx: HandlerCtx, *, edit: bool = False) -> None:
    """Кредиторка — поставщики, кому мы должны. Берём из PurchaseOrder."""
    from apps.purchases.models import PurchaseOrder

    org = ctx.org()
    debts = list(
        PurchaseOrder.objects
        .filter(organization=org, status=PurchaseOrder.Status.CONFIRMED)
        .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
        .annotate(remaining=F("amount_uzs") - F("paid_amount_uzs"))
        .filter(remaining__gt=0)
        .select_related("supplier")
        .order_by("-remaining")[:5]
    )

    lines = ["📤 <b>Кредиторка — топ-5</b>", ""]
    if not debts:
        lines.append("✅ Все закупки оплачены.")
    else:
        total = Decimal("0")
        for po in debts:
            supplier = po.supplier.name if po.supplier_id else "—"
            lines.append(
                f"• <b>{supplier}</b>\n"
                f"  <code>{po.doc_number}</code> · "
                f"<code>{_fmt_uzs(po.remaining)}</code> сум"
            )
            total += po.remaining
        lines.append("")
        lines.append(f"💼 <b>Итого по топ-5:</b> <code>{_fmt_uzs(total)}</code> сум")

    text = "\n".join(lines)
    markup = kb_back("home:fin")
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /pnl ────────────────────────────────────────────────────────────────


@command("/pnl", help="P&L за период (день/неделя/месяц)", module="reports")
def handle_pnl_cmd(ctx: HandlerCtx) -> None:
    period = (ctx.args[0] if ctx.args else "week").lower()
    if period not in ("today", "week", "month"):
        period = "week"
    _render_pnl(ctx, period=period)


@on_callback("fin:pnl")
def handle_pnl_callback(ctx: HandlerCtx) -> None:
    """Callback `fin:pnl:week|month|today`."""
    if not _check_or_deny(ctx):
        return
    period = ctx.args[1] if len(ctx.args) >= 2 else "week"
    if period not in ("today", "week", "month"):
        period = "week"
    _render_pnl(ctx, period=period, edit=True)


def _render_pnl(ctx: HandlerCtx, *, period: str, edit: bool = False) -> None:
    from apps.accounting.services.reports import compute_pl_by_module, compute_pl_report

    org = ctx.org()
    df, dt = _period_range(period)

    base = compute_pl_report(org, date_from=df, date_to=dt)
    by_mod = compute_pl_by_module(org, date_from=df, date_to=dt)

    period_labels = {"today": "сегодня", "week": "неделя", "month": "месяц"}
    lines = [
        f"📈 <b>P&L · {period_labels[period]}</b>",
        f"<i>{df.isoformat()} — {dt.isoformat()}</i>",
        "",
        f"💚 Доходы:  <code>{_fmt_uzs(base.total_revenue)}</code>",
        f"❤️ Расходы: <code>{_fmt_uzs(base.total_expense)}</code>",
        "─" * 18,
    ]
    profit = base.profit
    sign = "🟢" if profit >= 0 else "🔴"
    lines.append(f"{sign} <b>Прибыль:</b> <code>{_fmt_uzs(profit)}</code> сум")

    if by_mod.rows:
        lines.append("")
        lines.append("<b>По модулям:</b>")
        for r in by_mod.rows[:6]:
            mark = "▲" if r.profit >= 0 else "▼"
            lines.append(
                f"  {mark} {r.module_name}: <code>{_fmt_uzs(r.profit)}</code>"
            )

    text = "\n".join(lines)
    markup = {
        "inline_keyboard":
            kb_periods("fin:pnl", current=period)["inline_keyboard"]
            + kb_back("home:fin")["inline_keyboard"]
    }
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── /sales ──────────────────────────────────────────────────────────────


@command("/sales", help="Продажи за период (день/неделя/месяц)", module="reports")
def handle_sales_cmd(ctx: HandlerCtx) -> None:
    period = (ctx.args[0] if ctx.args else "week").lower()
    if period not in ("today", "week", "month"):
        period = "week"
    _render_sales(ctx, period=period)


@on_callback("fin:sales")
def handle_sales_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx):
        return
    period = ctx.args[1] if len(ctx.args) >= 2 else "week"
    if period not in ("today", "week", "month"):
        period = "week"
    _render_sales(ctx, period=period, edit=True)


def _render_sales(ctx: HandlerCtx, *, period: str, edit: bool = False) -> None:
    from django.db.models import Count, Sum
    from apps.sales.models import SaleOrder

    org = ctx.org()
    df, dt = _period_range(period)

    qs = SaleOrder.objects.filter(
        organization=org, status=SaleOrder.Status.CONFIRMED,
        date__gte=df, date__lte=dt,
    )
    agg = qs.aggregate(n=Count("id"), s=Sum("amount_uzs"))
    n = agg["n"] or 0
    total = agg["s"] or Decimal("0")
    top = list(
        qs.select_related("customer").order_by("-amount_uzs")[:5]
    )

    period_labels = {"today": "сегодня", "week": "неделя", "month": "месяц"}
    lines = [
        f"💸 <b>Продажи · {period_labels[period]}</b>",
        f"<i>{df.isoformat()} — {dt.isoformat()}</i>",
        "",
        f"Документов: <b>{n}</b>",
        f"Сумма: <code>{_fmt_uzs(total)}</code> сум",
    ]
    if top:
        lines.append("")
        lines.append("<b>Топ-5:</b>")
        for so in top:
            customer = so.customer.name if so.customer_id else "—"
            lines.append(
                f"  • {customer} · <code>{so.doc_number}</code> · "
                f"<code>{_fmt_uzs(so.amount_uzs)}</code>"
            )

    text = "\n".join(lines)
    markup = {
        "inline_keyboard":
            kb_periods("fin:sales", current=period)["inline_keyboard"]
            + kb_back("home:fin")["inline_keyboard"]
    }
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)
