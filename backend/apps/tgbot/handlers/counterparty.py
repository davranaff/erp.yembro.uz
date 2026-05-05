"""
Клиент-кабинет в TG-боте: только для counterparty-link.

Команды (все на узбекском):
  /menu          — главное меню клиента
  /buyurtmalar   — мои заказы (последние 10 + общая сумма / долг)
  /qarz          — моя задолженность (с разбивкой по заказам и сроком)
  /holat         — статус блокировки (если у меня есть просрочка/превышение
                   лимита — что меня ждёт + сколько отдать)

Безопасность: handler'ы работают только с counterparty-link (audience=
"counterparty"). Dispatcher гейтит. Все запросы scope'нутся к
link.counterparty.
"""
from __future__ import annotations

from datetime import date as _date
from decimal import Decimal

from django.db.models import Sum

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb


# ─── helpers ──────────────────────────────────────────────────────────────


def _fmt_money(v) -> str:
    try:
        return f"{float(v):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


def _send_or_edit(ctx, text, markup):
    if ctx.message_id:
        edit_message_text(ctx.chat_id, ctx.message_id, text, reply_markup=markup)
    else:
        send_message(ctx.chat_id, text, reply_markup=markup)


def _menu_keyboard():
    return kb([
        ("📦 Buyurtmalarim", "cp:orders"),
        ("💰 Qarzdorligim", "cp:debt"),
        ("🚫 Bloklash holati", "cp:holat"),
    ], cols=1)


def _back_kb():
    return kb([("← Orqaga", "cp:menu")], cols=1)


# ─── /menu (для counterparty) ────────────────────────────────────────────


def render_counterparty_menu(ctx: HandlerCtx) -> None:
    """Главное меню клиента — вызывается из handlers/menu.py если link это cp."""
    cp = ctx.link.counterparty
    text = (
        f"👋 <b>Salom, {cp.name}!</b>\n\n"
        "Quyidagi bo'limlardan birini tanlang:"
    )
    _send_or_edit(ctx, text, _menu_keyboard())


@on_callback("cp:menu")
def handle_cp_menu_callback(ctx: HandlerCtx) -> None:
    render_counterparty_menu(ctx)


# ─── /buyurtmalar ─────────────────────────────────────────────────────────


@command("/buyurtmalar", help="Mening buyurtmalarim", audience="counterparty")
def handle_orders_cmd(ctx: HandlerCtx) -> None:
    _render_orders(ctx)


@on_callback("cp:orders")
def handle_orders_callback(ctx: HandlerCtx) -> None:
    _render_orders(ctx)


def _render_orders(ctx: HandlerCtx) -> None:
    """Последние 10 confirmed-заказов клиента с paid/debt разрезом."""
    from apps.sales.models import SaleOrder

    cp = ctx.link.counterparty
    qs = (
        SaleOrder.objects
        .filter(
            organization=ctx.link.organization_id,
            customer=cp,
            status=SaleOrder.Status.CONFIRMED,
        )
        .order_by("-date", "-created_at")[:10]
    )
    orders = list(qs)

    lines = [f"📦 <b>{cp.name} — buyurtmalaringiz</b>", ""]
    if not orders:
        lines.append("Hozircha buyurtmalar yo'q.")
    else:
        for o in orders:
            total = Decimal(o.amount_uzs or 0)
            paid = Decimal(o.paid_amount_uzs or 0)
            debt = total - paid
            status_icon = "✅" if debt <= 0 else "⏳"
            line = (
                f"{status_icon} <code>{o.doc_number}</code> · {o.date}\n"
                f"   Summa: <b>{_fmt_money(total)}</b> so'm"
            )
            if debt > 0:
                line += f"\n   Qarz: <b>{_fmt_money(debt)}</b> so'm"
                if o.due_date:
                    delta = (o.due_date - _date.today()).days
                    if delta < 0:
                        line += f" · 🚨 {abs(delta)} kun kechikdi"
                    elif delta == 0:
                        line += " · ⚠️ bugun muddat"
                    else:
                        line += f" · {delta} kun qoldi"
            else:
                line += " · ✅ to'liq to'langan"
            lines.append(line)

    _send_or_edit(ctx, "\n".join(lines), _back_kb())


# ─── /qarz ────────────────────────────────────────────────────────────────


@command("/qarz", help="Qarzdorligim", audience="counterparty")
def handle_debt_cmd(ctx: HandlerCtx) -> None:
    _render_debt(ctx)


@on_callback("cp:debt")
def handle_debt_callback(ctx: HandlerCtx) -> None:
    _render_debt(ctx)


def _render_debt(ctx: HandlerCtx) -> None:
    """Сумма долга + список неоплаченных заказов."""
    from apps.sales.models import SaleOrder

    cp = ctx.link.counterparty
    unpaid_qs = (
        SaleOrder.objects
        .filter(
            organization=ctx.link.organization_id,
            customer=cp,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .order_by("date")
    )
    unpaid = list(unpaid_qs)
    total_debt = sum(
        (Decimal(o.amount_uzs or 0) - Decimal(o.paid_amount_uzs or 0))
        for o in unpaid
    )

    if not unpaid:
        text = (
            f"✨ <b>{cp.name}</b>\n\n"
            "Sizda qarzdorlik yo'q. Rahmat! ❤️"
        )
        _send_or_edit(ctx, text, _back_kb())
        return

    lines = [
        f"💰 <b>Sizning qarzdorligingiz</b>",
        f"<i>{cp.name}</i>",
        "",
        f"Jami qarz: <b>{_fmt_money(total_debt)}</b> so'm",
        f"To'lanmagan buyurtmalar: <b>{len(unpaid)}</b>",
        "",
        "<b>Buyurtmalar bo'yicha:</b>",
    ]
    for o in unpaid[:10]:
        debt = Decimal(o.amount_uzs or 0) - Decimal(o.paid_amount_uzs or 0)
        line = f"• <code>{o.doc_number}</code> · {_fmt_money(debt)} so'm"
        if o.due_date:
            delta = (o.due_date - _date.today()).days
            if delta < 0:
                line += f" · 🚨 {abs(delta)} kun kechikdi"
            elif delta == 0:
                line += " · ⚠️ bugun"
        lines.append(line)
    if len(unpaid) > 10:
        lines.append(f"… va yana {len(unpaid) - 10} ta buyurtma")
    lines.append("")
    lines.append("💳 Iltimos, to'lovni o'z vaqtida amalga oshiring.")

    _send_or_edit(ctx, "\n".join(lines), _back_kb())


# ─── /holat ───────────────────────────────────────────────────────────────


@command("/holat", help="Bloklash holati", audience="counterparty")
def handle_status_cmd(ctx: HandlerCtx) -> None:
    _render_block_status(ctx)


@on_callback("cp:holat")
def handle_status_callback(ctx: HandlerCtx) -> None:
    _render_block_status(ctx)


def _render_block_status(ctx: HandlerCtx) -> None:
    """Покажет клиенту: заблокирован ли он от новых покупок и почему.

    Используется тот же check_customer_credit что бэк дёргает на confirm —
    единая правда. Если ok=True → «можете покупать». Если ok=False —
    показываем причины и сколько надо погасить.
    """
    from apps.sales.services.credit_check import check_customer_credit

    cp = ctx.link.counterparty
    org_id = ctx.link.organization_id
    # Симулируем «новая продажа = 0» — проверяем текущее состояние без
    # учёта будущих покупок. Если уже сейчас не ok — клиент заблокирован.
    from apps.organizations.models import Organization
    org = Organization.objects.get(id=org_id)
    result = check_customer_credit(
        organization=org, customer=cp, new_sale_uzs=Decimal("0"),
    )

    if result.ok:
        lines = [
            "✅ <b>Holat: faol</b>",
            "",
            f"<i>{cp.name}</i>",
            "",
            f"Joriy qarz: <b>{_fmt_money(result.current_debt_uzs)}</b> so'm",
        ]
        if result.limit_uzs is not None:
            available = result.limit_uzs - result.current_debt_uzs
            lines.append(
                f"Kredit limiti: {_fmt_money(result.limit_uzs)} so'm"
            )
            lines.append(
                f"Mavjud limit: <b>{_fmt_money(available)}</b> so'm"
            )
        lines.append("")
        lines.append("Siz xarid qilishingiz mumkin. ✨")
    else:
        lines = [
            "🚫 <b>Holat: bloklangan</b>",
            "",
            f"<i>{cp.name}</i>",
            "",
            f"Joriy qarz: <b>{_fmt_money(result.current_debt_uzs)}</b> so'm",
        ]
        if result.limit_uzs is not None:
            lines.append(f"Kredit limiti: {_fmt_money(result.limit_uzs)} so'm")
        if result.oldest_overdue > 0:
            lines.append(f"Eng eski kechikish: <b>{result.oldest_overdue}</b> kun")
        lines.append("")
        lines.append("<b>Sabab:</b>")
        for reason in result.reasons:
            lines.append(f"• {reason}")
        lines.append("")
        lines.append(
            "💳 Yangi xaridlar uchun mavjud qarzni to'lash kerak."
        )

    _send_or_edit(ctx, "\n".join(lines), _back_kb())
