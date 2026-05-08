"""
Финансовая секция бота: касса, дебиторка, кредиторка, P&L, продажи.

Главный приём: переиспользуем существующие сервисы
  - apps.dashboard.services.cash_balances / cashflow_chart
  - apps.accounting.services.reports.compute_pl_report / compute_pl_by_module
вместо того чтобы дублировать SQL.

Стиль сообщений: минималистичный. Один эмодзи в заголовке для visual cue,
числа в <code>, итоги в <b>, разделитель `─`. Без перегруза цветными
эмодзи — финансовые сводки должны читаться как бухгалтерская выписка.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import F, Sum

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, has_module_access, on_callback
from ..keyboards import (
    PAGE_SIZE,
    kb,
    kb_back,
    kb_back_home,
    kb_pagination,
    kb_periods,
    parse_page,
)

logger = logging.getLogger(__name__)


# ─── helpers ─────────────────────────────────────────────────────────────


def _fmt_uzs(value) -> str:
    """100_000_000 → '100 000 000'. Принимает Decimal/str/None."""
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


def _fmt_signed(value) -> str:
    """+12 500 000 / −1 200 000 / 0. Для P&L и net потока."""
    if value is None or value == "":
        return "0"
    n = Decimal(str(value))
    if n == 0:
        return "0"
    sign = "+" if n > 0 else "−"
    return f"{sign}{_fmt_uzs(abs(n))}"


def _ascii_sparkline(values: list[Decimal]) -> str:
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
    return today - timedelta(days=6), today


def _check_or_deny(ctx: HandlerCtx, *, modules: list[str] = None) -> bool:
    """Доступ если есть >=r на ХОТЯ БЫ ОДИН модуль из списка.

    Owner ('admin' модуль) — пускаем всегда. Без modules — старая
    проверка только на 'reports' (для совместимости).
    """
    from ..services.menu_scope import has_any_access, is_owner, user_module_levels

    levels = user_module_levels(ctx.link)
    if is_owner(levels):
        return True
    needed = modules or ["reports"]
    if has_any_access(levels, needed):
        return True
    send_message(ctx.chat_id, "⛔ Sizda bu bo'limga ruxsat yo'q.")
    return False


def _send_or_edit(
    ctx: HandlerCtx, text: str, markup: dict, *, edit: bool,
) -> None:
    if edit and ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


# ─── menu (callback `home:fin`) ─────────────────────────────────────────
# Каждый sub-раздел гейтится своим списком модулей. Юзер видит только
# те разделы, к которым у него есть доступ хотя бы к одному из модулей.


_FIN_SUB_BUTTONS = [
    # (label, callback, [required_modules])
    ("💵 Kassa/bank",   "fin:cash",        ["ledger", "reports"]),
    ("👥 Mijozlar qarzi", "fin:debt",       ["sales", "reports"]),
    ("🏢 Yetkazib beruvchi qarzi", "fin:cred", ["purchases", "reports"]),
    ("📈 P&L",           "fin:pnl:week",   ["reports", "ledger"]),
    ("💸 Sotuvlar",      "fin:sales:week", ["sales", "reports"]),
    ("📦 Sklad qoldiqlari", "fin:stock",   ["stock", "reports"]),
]


def render_finance_menu(ctx: HandlerCtx) -> None:
    from ..services.menu_scope import has_any_access, is_owner, user_module_levels

    levels = user_module_levels(ctx.link)
    if not is_owner(levels) and not any(
        has_any_access(levels, mods) for _, _, mods in _FIN_SUB_BUTTONS
    ):
        send_message(ctx.chat_id, "⛔ Sizda Moliya bo'limiga ruxsat yo'q.")
        return

    visible = [
        (label, cb) for label, cb, mods in _FIN_SUB_BUTTONS
        if is_owner(levels) or has_any_access(levels, mods)
    ]
    markup = kb(visible + [("← Orqaga", "home")], cols=2)
    _send_or_edit(
        ctx,
        "💰 <b>Moliya</b>\n\nBo'limni tanlang:",
        markup,
        edit=ctx.message_id is not None,
    )


# ─── /cash ───────────────────────────────────────────────────────────────


@command("/cash", help="Остатки кассы и банка + кэш-флоу 7 дн", module="reports")
def handle_cash_cmd(ctx: HandlerCtx) -> None:
    _render_cash(ctx)


@on_callback("fin:cash")
def handle_cash_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx, modules=["ledger", "reports"]):
        return
    _render_cash(ctx, edit=True)


def _render_cash(ctx: HandlerCtx, *, edit: bool = False) -> None:
    from apps.dashboard.services import cash_balances, cashflow_chart

    org = ctx.org()
    cash = cash_balances(org)
    points = cashflow_chart(org, days=7)

    # Cash-balance может быть отрицательным когда касса/счёт в овердрафте
    # (списали больше чем приходов — например операционные расходы оплачены
    # будущими поступлениями). Раньше выводили просто отрицательное число —
    # пользователю было непонятно почему.

    lines = ["💵 <b>Kassa va bank</b>", ""]
    has_negative = False
    channels = []
    for ch_key, ch_data in cash.items():
        if ch_key.startswith("_"):
            continue
        bal_dec = Decimal(str(ch_data["balance_uzs"]))
        if bal_dec < 0:
            has_negative = True
            mark = "!"
        elif bal_dec == 0:
            mark = "·"
        else:
            mark = "+"
        channels.append((mark, ch_data["label"], bal_dec))

    if channels:
        # Моноширинная таблица: маркер · канал · баланс.
        name_w = max(6, min(20, max(len(label) for _, label, _ in channels)))
        rows_text = []
        for mark, label, bal in channels:
            label_t = label[:name_w]
            bal_str = (
                f"-{_fmt_uzs(abs(bal))}" if bal < 0
                else ("0" if bal == 0 else _fmt_uzs(bal))
            )
            rows_text.append(f"{mark} {label_t:<{name_w}}  {bal_str:>14} so'm")
        # Итого отдельной строкой с разделителем.
        total_dec = Decimal(str(cash["_total_uzs"]))
        total_str = (
            f"-{_fmt_uzs(abs(total_dec))}" if total_dec < 0
            else _fmt_uzs(total_dec)
        )
        sep_w = name_w + 2 + 14 + 5  # mark + name + 2sp + bal + " so'm"
        rows_text.append("─" * sep_w)
        rows_text.append(f"  Jami{' ' * (name_w - 2)}  {total_str:>14} so'm")
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")

    if has_negative:
        lines.append(
            "<i>! manfiy qoldiq — chiqim kirimdan ko'p (overdraft yoki "
            "dastlabki qoldiq sozlanmagan).</i>"
        )

    if points:
        # Cashflow 7 дней — отдельная мини-таблица.
        in_total = sum((Decimal(p["in_uzs"]) for p in points), Decimal("0"))
        out_total = sum((Decimal(p["out_uzs"]) for p in points), Decimal("0"))
        net_total = in_total - out_total
        lines.append("")
        lines.append("<b>Cash-flow · 7 kun</b>")
        lines.append(
            "<pre>"
            f"Kirim   {_fmt_uzs(in_total):>14} so'm\n"
            f"Chiqim  {_fmt_uzs(out_total):>14} so'm\n"
            f"Saldo   {_fmt_signed(net_total):>14} so'm"
            "</pre>"
        )

    _send_or_edit(ctx, "\n".join(lines), kb_back_home("home:fin"), edit=edit)


# ─── /debt ───────────────────────────────────────────────────────────────


@command("/debt", help="Топ-5 должников", module="reports")
def handle_debt_cmd(ctx: HandlerCtx) -> None:
    _render_debt(ctx)


@on_callback("noop")
def handle_noop_callback(ctx: HandlerCtx) -> None:
    """Pagination-плашка «3/7» — кликабельна но ничего не делает.
    Telegram требует ответ за 15с — answer_callback_query уже дёрнут
    в dispatcher до handler'а."""
    return


# ─── Excel-выгрузки on-demand (callback `dl:debtors` / `dl:stock`) ───────


@on_callback("dl:debtors")
def handle_download_debtors(ctx: HandlerCtx) -> None:
    """Сгенерить и сразу прислать файл со списком должников.

    Тот же отчёт что в 22:00 рассылается автоматически — но юзер может
    запросить когда захочет, не дожидаясь ночи.
    """
    if not _check_or_deny(ctx, modules=["sales", "reports"]):
        return
    from datetime import date as _date

    from ..bot import send_document, send_message
    from ..services.excel_reports import (
        debtors_filename,
        generate_debtors_xlsx,
    )

    org = ctx.org()
    today = _date.today()
    try:
        blob = generate_debtors_xlsx(org, today=today)
    except Exception:  # noqa: BLE001
        logger.exception("dl:debtors: build failed for org=%s", org.code)
        send_message(ctx.chat_id, "❌ Hisobot tayyorlashda xato yuz berdi.")
        return

    fname = debtors_filename(today)
    caption = f"💼 Mijoz qarzlari · {today.isoformat()}"
    send_document(ctx.chat_id, blob, fname, caption=caption)


@on_callback("dl:stock")
def handle_download_stock(ctx: HandlerCtx) -> None:
    """Сгенерить и сразу прислать файл с остатками по всем складам.

    Колонки: Склад / Модуль / SKU / Наименование / Ед / Σ Приход /
    Σ Расход / Остаток. Каждая пара (склад, SKU) — отдельная строка,
    т.е. видно остатки досконально по каждому складу.
    """
    if not _check_or_deny(ctx, modules=["stock", "reports", "ledger"]):
        return
    from datetime import date as _date

    from ..bot import send_document, send_message
    from ..services.excel_reports import (
        generate_stock_balance_xlsx,
        stock_filename,
    )

    org = ctx.org()
    today = _date.today()
    try:
        blob = generate_stock_balance_xlsx(org, today=today)
    except Exception:  # noqa: BLE001
        logger.exception("dl:stock: build failed for org=%s", org.code)
        send_message(ctx.chat_id, "❌ Hisobot tayyorlashda xato yuz berdi.")
        return

    fname = stock_filename(today)
    caption = f"📦 Sklad qoldiqlari · {today.isoformat()}"
    send_document(ctx.chat_id, blob, fname, caption=caption)


@on_callback("fin:debt")
def handle_debt_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx, modules=["sales", "reports"]):
        return
    page = parse_page(ctx.args)
    _render_debt(ctx, page=page, edit=True)


def _render_debt(ctx: HandlerCtx, *, page: int = 1, edit: bool = False) -> None:
    from apps.sales.models import SaleOrder

    org = ctx.org()
    today = date.today()

    base_qs = (
        SaleOrder.objects
        .filter(organization=org, status=SaleOrder.Status.CONFIRMED)
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .annotate(remaining=F("amount_uzs") - F("paid_amount_uzs"))
        .filter(remaining__gt=0)
        .select_related("customer")
        .order_by("-remaining")
    )
    total_count = base_qs.count()
    grand_total = (
        base_qs.aggregate(s=Sum("remaining"))["s"] or Decimal("0")
    ) if total_count else Decimal("0")

    pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    offset = (page - 1) * PAGE_SIZE
    debts = list(base_qs[offset:offset + PAGE_SIZE])

    lines = [
        "📥 <b>Mijoz qarzlari</b>",
        "<i>kim bizga qarzdor</i>",
        "",
    ]
    if total_count == 0:
        lines.append("Barcha sotuvlar to'langan.")
        markup = kb_back_home("home:fin")
    else:
        lines.append(
            f"Jami {total_count} ta hujjat · <b>{_fmt_uzs(grand_total)}</b> so'm"
        )
        lines.append("")
        # Моноширинная таблица: №, doc, клиент, сумма, дни просрочки.
        doc_w = max(8, min(14, max(len(so.doc_number) for so in debts)))
        name_w = max(10, min(22, max(len(so.customer.name if so.customer_id else "—") for so in debts)))
        rows_text = []
        for i, so in enumerate(debts, offset + 1):
            customer = (so.customer.name if so.customer_id else "—")[:name_w]
            doc = so.doc_number[:doc_w]
            overdue = (today - so.due_date).days if so.due_date and so.due_date < today else 0
            ov = f"{overdue}d" if overdue > 0 else "—"
            rows_text.append(
                f"{i:>2} {doc:<{doc_w}}  {customer:<{name_w}}  "
                f"{_fmt_uzs(so.remaining):>13}  {ov:>4}"
            )
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")
        # «kechikkan» — узб. «опоздал/просрочка». Подпись для UI и для
        # совместимости с существующими тестами.
        lines.append("<i>колонки: №, doc, mijoz, qarz, kun kechikkan</i>")
        markup = kb_pagination("fin:debt", page, total_count, back_to="home:fin")

    _send_or_edit(ctx, "\n".join(lines), markup, edit=edit)


# ─── /cred (топ-5 кредиторов) ────────────────────────────────────────────


@on_callback("fin:cred")
def handle_cred_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx, modules=["purchases", "reports"]):
        return
    page = parse_page(ctx.args)
    _render_cred(ctx, page=page, edit=True)


def _render_cred(ctx: HandlerCtx, *, page: int = 1, edit: bool = False) -> None:
    """Кредиторка — кому мы должны (10 на стр + пагинация)."""
    from apps.purchases.models import PurchaseOrder

    org = ctx.org()
    base_qs = (
        PurchaseOrder.objects
        .filter(
            organization=org,
            status__in=[
                PurchaseOrder.Status.CONFIRMED,
                PurchaseOrder.Status.PAID,
            ],
        )
        .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
        .annotate(remaining=F("amount_uzs") - F("paid_amount_uzs"))
        .filter(remaining__gt=0)
        .select_related("counterparty")
        .order_by("-remaining")
    )
    total_count = base_qs.count()
    grand_total = (
        base_qs.aggregate(s=Sum("remaining"))["s"] or Decimal("0")
    ) if total_count else Decimal("0")

    pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    offset = (page - 1) * PAGE_SIZE
    debts = list(base_qs[offset:offset + PAGE_SIZE])

    lines = [
        "📤 <b>Yetkazib beruvchi qarzlari</b>",
        "<i>biz kimga qarzdormiz</i>",
        "",
    ]
    if total_count == 0:
        lines.append("Barcha xaridlar to'langan.")
        markup = kb_back_home("home:fin")
    else:
        lines.append(
            f"Jami {total_count} ta hujjat · <b>{_fmt_uzs(grand_total)}</b> so'm"
        )
        lines.append("")
        doc_w = max(8, min(14, max(len(po.doc_number) for po in debts)))
        name_w = max(10, min(24, max(len(po.counterparty.name if po.counterparty_id else "—") for po in debts)))
        rows_text = []
        for i, po in enumerate(debts, offset + 1):
            supplier = (po.counterparty.name if po.counterparty_id else "—")[:name_w]
            doc = po.doc_number[:doc_w]
            rows_text.append(
                f"{i:>2} {doc:<{doc_w}}  {supplier:<{name_w}}  "
                f"{_fmt_uzs(po.remaining):>13}"
            )
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")
        lines.append("<i>колонки: №, doc, etkazib beruvchi, qarz</i>")
        markup = kb_pagination("fin:cred", page, total_count, back_to="home:fin")

    _send_or_edit(ctx, "\n".join(lines), markup, edit=edit)


# ─── /pnl ────────────────────────────────────────────────────────────────


_PERIOD_LABELS = {"today": "сегодня", "week": "неделя", "month": "месяц"}


@command("/pnl", help="P&L за период (день/неделя/месяц)", module="reports")
def handle_pnl_cmd(ctx: HandlerCtx) -> None:
    period = (ctx.args[0] if ctx.args else "week").lower()
    if period not in _PERIOD_LABELS:
        period = "week"
    _render_pnl(ctx, period=period)


@on_callback("fin:pnl")
def handle_pnl_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx, modules=["reports", "ledger"]):
        return
    # callback «fin:pnl:week» → ctx.args = [«week»] после фикса dispatcher.
    period = ctx.args[0] if ctx.args else "week"
    if period not in _PERIOD_LABELS:
        period = "week"
    _render_pnl(ctx, period=period, edit=True)


def _render_pnl(ctx: HandlerCtx, *, period: str, edit: bool = False) -> None:
    """P&L за период с разрезом «оплачено / задолженность».

    P&L по бухгалтерии — accrual-basis: продал на 50М, признал доход 50М,
    хотя клиент дал только 1М. В скобках показываем cash-картинку:
    сколько из этих 50М реально пришло на счёт, сколько висит долгом.
    Аналогично для расходов (закупки, оплаченные/нет).
    """
    from decimal import Decimal

    from django.db.models import Sum

    from apps.accounting.services.reports import compute_pl_by_module, compute_pl_report
    from apps.purchases.models import PurchaseOrder
    from apps.sales.models import SaleOrder

    org = ctx.org()
    df, dt = _period_range(period)
    base = compute_pl_report(org, date_from=df, date_to=dt)
    by_mod = compute_pl_by_module(org, date_from=df, date_to=dt)

    # Cash-разрез: продажи и закупки за тот же период (только confirmed,
    # не cancelled).
    sales_agg = (
        SaleOrder.objects
        .filter(
            organization=org,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=df, date__lte=dt,
        )
        .aggregate(
            total=Sum("amount_uzs"),
            paid=Sum("paid_amount_uzs"),
        )
    )
    sales_total = Decimal(sales_agg["total"] or 0)
    sales_paid = Decimal(sales_agg["paid"] or 0)
    sales_debt = sales_total - sales_paid

    purchases_agg = (
        PurchaseOrder.objects
        .filter(
            organization=org,
            status=PurchaseOrder.Status.CONFIRMED,
            date__gte=df, date__lte=dt,
        )
        .aggregate(
            total=Sum("amount_uzs"),
            paid=Sum("paid_amount_uzs"),
        )
    )
    purchases_total = Decimal(purchases_agg["total"] or 0)
    purchases_paid = Decimal(purchases_agg["paid"] or 0)
    purchases_debt = purchases_total - purchases_paid

    lines = [
        f"📈 <b>P&amp;L · {_PERIOD_LABELS[period]}</b>",
        f"<i>{df.isoformat()} — {dt.isoformat()}</i>",
        "",
    ]
    # Основная P&L-таблица (accrual basis) — вертикально, для ясности.
    pl_rows = [
        f"Доходы    {_fmt_uzs(base.total_revenue):>14}",
        f"Расходы   {_fmt_uzs(base.total_expense):>14}",
        "─" * 26,
        f"Прибыль   {_fmt_signed(base.profit):>14}",
    ]
    lines.append("<pre>" + "\n".join(pl_rows) + "</pre>")

    # Cash-разрез — таблица 3 колонки (сумма / оплачено / долг).
    if sales_total > 0 or purchases_total > 0:
        lines.append("<b>Деньги (cash basis):</b>")
        cash_rows = [f"{'':<11}{'сумма':>14}{'оплачено':>14}{'долг':>14}"]
        if sales_total > 0:
            cash_rows.append(
                f"{'Продано':<11}"
                f"{_fmt_uzs(sales_total):>14}"
                f"{_fmt_uzs(sales_paid):>14}"
                f"{_fmt_uzs(sales_debt):>14}"
            )
        if purchases_total > 0:
            cash_rows.append(
                f"{'Закуплено':<11}"
                f"{_fmt_uzs(purchases_total):>14}"
                f"{_fmt_uzs(purchases_paid):>14}"
                f"{_fmt_uzs(purchases_debt):>14}"
            )
        lines.append("<pre>" + "\n".join(cash_rows) + "</pre>")

    if by_mod.rows:
        lines.append("")
        lines.append("<b>По модулям:</b>")
        rows_show = by_mod.rows[:8]
        name_w = max(8, min(20, max(len(r.module_name) for r in rows_show)))
        rows_text = []
        for r in rows_show:
            mod_name = r.module_name[:name_w]
            rows_text.append(
                f"{mod_name:<{name_w}}  {_fmt_signed(r.profit):>14}"
            )
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")

    markup = {
        "inline_keyboard":
            kb_periods("fin:pnl", current=period)["inline_keyboard"]
            + kb_back("home:fin")["inline_keyboard"]
    }
    _send_or_edit(ctx, "\n".join(lines), markup, edit=edit)


# ─── /sales ──────────────────────────────────────────────────────────────


@command("/sales", help="Продажи за период (день/неделя/месяц)", module="reports")
def handle_sales_cmd(ctx: HandlerCtx) -> None:
    period = (ctx.args[0] if ctx.args else "week").lower()
    if period not in _PERIOD_LABELS:
        period = "week"
    _render_sales(ctx, period=period)


@on_callback("fin:sales")
def handle_sales_callback(ctx: HandlerCtx) -> None:
    if not _check_or_deny(ctx, modules=["sales", "reports"]):
        return
    # callback «fin:sales:week» → ctx.args = [«week»] после фикса dispatcher.
    period = ctx.args[0] if ctx.args else "week"
    if period not in _PERIOD_LABELS:
        period = "week"
    _render_sales(ctx, period=period, edit=True)


def _render_sales(ctx: HandlerCtx, *, period: str, edit: bool = False) -> None:
    """Продажи за период с разрезом «оплачено / должны».

    Раньше показывали только сумму отгрузок (50М). Бизнес-проблема:
    цифра вводила в заблуждение — клиент мог отдать только 1М, а 49М
    висеть в дебиторке. Теперь рядом с каждой суммой видно paid/debt.
    """
    from django.db.models import Count, Sum
    from apps.sales.models import SaleOrder

    org = ctx.org()
    df, dt = _period_range(period)

    qs = SaleOrder.objects.filter(
        organization=org, status=SaleOrder.Status.CONFIRMED,
        date__gte=df, date__lte=dt,
    )
    agg = qs.aggregate(
        n=Count("id"),
        s=Sum("amount_uzs"),
        p=Sum("paid_amount_uzs"),
    )
    n = agg["n"] or 0
    total = agg["s"] or Decimal("0")
    paid = agg["p"] or Decimal("0")
    debt = total - paid
    pct_paid = (paid / total * 100) if total > 0 else Decimal("0")
    # 10 на странице + пагинация. callback: «fin:sales:p:<period>:<page>».
    # Страница берётся из ctx.args (callback может прислать period+page).
    page = 1
    if len(ctx.args) >= 2:
        try:
            page = max(1, int(ctx.args[1]))
        except (ValueError, TypeError):
            page = 1

    base_qs = qs.select_related("customer").order_by("-amount_uzs")
    pages = max(1, (n + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, pages))
    offset = (page - 1) * PAGE_SIZE
    rows = list(base_qs[offset:offset + PAGE_SIZE])

    lines = [
        f"💸 <b>Sotuvlar · {_PERIOD_LABELS[period]}</b>",
        f"<i>{df.isoformat()} — {dt.isoformat()}</i>",
        "",
        f"  Hujjatlar:    <b>{n}</b>",
        f"  Otgruzilgan:  <code>{_fmt_uzs(total)}</code> so'm",
        f"  ↳ to'langan:  <code>{_fmt_uzs(paid)}</code> ({pct_paid:.0f}%)",
        f"  ↳ qarz:       <code>{_fmt_uzs(debt)}</code> so'm",
    ]
    if rows:
        lines.append("")
        lines.append(f"<b>Hujjatlar (sahifa {page}/{pages}):</b>")
        # Моноширинная таблица: №, doc, клиент, сумма, долг (или ✓).
        doc_w = max(8, min(14, max(len(so.doc_number) for so in rows)))
        name_w = max(8, min(20, max(len(so.customer.name if so.customer_id else "—") for so in rows)))
        rows_text = []
        for i, so in enumerate(rows, offset + 1):
            customer = (so.customer.name if so.customer_id else "—")[:name_w]
            doc = so.doc_number[:doc_w]
            so_total = Decimal(so.amount_uzs or 0)
            so_debt = so_total - Decimal(so.paid_amount_uzs or 0)
            debt_str = "to'langan" if so_debt <= 0 else _fmt_uzs(so_debt)
            rows_text.append(
                f"{i:>2} {doc:<{doc_w}}  {customer:<{name_w}}  "
                f"{_fmt_uzs(so_total):>13}  {debt_str:>10}"
            )
        lines.append("<pre>" + "\n".join(rows_text) + "</pre>")
        lines.append("<i>колонки: №, doc, mijoz, summa, qarz</i>")

    # Пагинация переключает страницу: callback «fin:sales:<period>:<N>».
    nav: list[tuple[str, str]] = []
    if page > 1:
        nav.append(("← Oldingi", f"fin:sales:{period}:{page - 1}"))
    nav.append((f"{page}/{pages}", "noop"))
    if page < pages:
        nav.append(("Keyingi →", f"fin:sales:{period}:{page + 1}"))

    inline = (
        kb_periods("fin:sales", current=period)["inline_keyboard"]
        + [[{"text": t, "callback_data": cb} for t, cb in nav]]
        + kb_back("home:fin")["inline_keyboard"]
    )
    _send_or_edit(ctx, "\n".join(lines), {"inline_keyboard": inline}, edit=edit)
