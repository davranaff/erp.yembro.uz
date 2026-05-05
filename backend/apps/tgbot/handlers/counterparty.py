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
    """Последние 10 confirmed-заказов клиента с paid/debt разрезом + сводка
    и кнопки drill-down на каждый заказ."""
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

    # Сводка по последним 10
    sum_total = sum(Decimal(o.amount_uzs or 0) for o in orders)
    sum_paid = sum(Decimal(o.paid_amount_uzs or 0) for o in orders)
    sum_debt = sum_total - sum_paid

    lines = [f"📦 <b>Buyurtmalaringiz</b>", f"<i>{cp.name}</i>", ""]
    if not orders:
        lines.append("Hozircha buyurtmalar yo'q.")
        _send_or_edit(ctx, "\n".join(lines), _back_kb())
        return

    lines.append(f"Oxirgi {len(orders)} ta buyurtma:")
    lines.append(f"  Jami summa:  <b>{_fmt_money(sum_total)}</b> so'm")
    lines.append(f"  To'langan:   <b>{_fmt_money(sum_paid)}</b> so'm")
    lines.append(f"  Qarz:        <b>{_fmt_money(sum_debt)}</b> so'm")
    lines.append("")

    buttons = []
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
        # Кнопка drill-down на детали заказа
        buttons.append((f"📄 {o.doc_number}", f"cp:order:{o.id}"))

    # Делим клавиатуру: сначала кнопки заказов, потом «← Назад»
    markup = kb(buttons[:8] + [("← Orqaga", "cp:menu")], cols=2)
    _send_or_edit(ctx, "\n".join(lines), markup)


# ─── Детали одного заказа: позиции + платежи ──────────────────────────────


@on_callback("cp:order")
def handle_order_detail_callback(ctx: HandlerCtx) -> None:
    if not ctx.args:
        return
    _render_order_detail(ctx, order_id=ctx.args[0])


def _render_order_detail(ctx: HandlerCtx, *, order_id: str) -> None:
    """Карточка заказа: что купили (позиции) + история платежей."""
    from apps.payments.models import Payment, PaymentAllocation
    from apps.sales.models import SaleOrder

    cp = ctx.link.counterparty
    order = (
        SaleOrder.objects
        .filter(
            id=order_id,
            organization=ctx.link.organization_id,
            customer=cp,
        )
        .select_related("currency", "warehouse")
        .first()
    )
    if order is None:
        send_message(ctx.chat_id, "❌ Buyurtma topilmadi.")
        return

    total = Decimal(order.amount_uzs or 0)
    paid = Decimal(order.paid_amount_uzs or 0)
    debt = total - paid

    lines = [
        f"📄 <b>Buyurtma {order.doc_number}</b>",
        f"📅 Sana: {order.date}",
        f"💰 Summa: <b>{_fmt_money(total)}</b> so'm",
        f"✅ To'langan: <b>{_fmt_money(paid)}</b> so'm",
    ]
    if debt > 0:
        lines.append(f"⏳ Qarz: <b>{_fmt_money(debt)}</b> so'm")
        if order.due_date:
            lines.append(f"📆 To'lov muddati: {order.due_date}")
    else:
        lines.append("✅ To'liq to'langan")
    lines.append("")

    # Позиции
    items = list(
        order.items.select_related(
            "nomenclature", "feed_batch", "feed_bag_lot", "vet_stock_batch",
            "vet_accessory", "batch",
        )
    )
    if items:
        lines.append("<b>Pozitsiyalar:</b>")
        for it in items:
            nom = it.nomenclature.name if it.nomenclature_id else "—"
            unit = ""
            if it.feed_bag_lot_id:
                unit = "qop"
            elif it.feed_batch_id:
                unit = "kg"
            elif it.batch_id and it.batch.unit_id:
                unit = it.batch.unit.code
            qty_str = f"{int(float(it.quantity)):,}".replace(",", " ") \
                if float(it.quantity) == int(float(it.quantity)) \
                else f"{float(it.quantity):,.3f}".rstrip("0").rstrip(".")
            lines.append(
                f"  • {nom} · {qty_str} {unit} × "
                f"{_fmt_money(it.unit_price_uzs)} = "
                f"<b>{_fmt_money(it.line_total_uzs)}</b> so'm"
            )
        lines.append("")

    # История платежей по этому заказу через PaymentAllocation
    from django.contrib.contenttypes.models import ContentType
    so_ct = ContentType.objects.get_for_model(SaleOrder)
    payments = (
        Payment.objects
        .filter(
            organization=ctx.link.organization_id,
            allocations__target_content_type=so_ct,
            allocations__target_object_id=order.id,
            status=Payment.Status.POSTED,
        )
        .order_by("date", "created_at")
        .distinct()
    )
    if payments:
        lines.append("<b>To'lovlar tarixi:</b>")
        for p in payments:
            allocs = PaymentAllocation.objects.filter(
                payment=p,
                target_content_type=so_ct,
                target_object_id=order.id,
            )
            alloc_sum = sum(Decimal(a.amount_uzs or 0) for a in allocs)
            lines.append(
                f"  • {p.date} · {p.get_channel_display()} · "
                f"<b>{_fmt_money(alloc_sum)}</b> so'm"
            )
    elif paid > 0:
        lines.append(f"To'langan: {_fmt_money(paid)} so'm")

    _send_or_edit(
        ctx, "\n".join(lines),
        kb([("← Buyurtmalar", "cp:orders"), ("🏠 Bosh menyu", "cp:menu")], cols=2),
    )


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
            f"💰 <b>Qarzdorlik holati</b>\n"
            f"<i>{cp.name}</i>\n\n"
            "To'lanmagan buyurtmalar yo'q."
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
    """Показ клиенту: заблокирован ли он от новых покупок и фактический долг.

    check_customer_credit хорош для решения «блокировать или нет», но его
    fast-path возвращает current_debt_uzs=0 для клиентов БЕЗ настроенных
    лимитов (что встречается чаще всего). Для отображения реального долга
    считаем сами через aging-report — единая логика с /qarz командой.
    """
    from apps.organizations.models import Organization
    from apps.sales.models import SaleOrder
    from apps.sales.services.credit_check import check_customer_credit

    cp = ctx.link.counterparty
    org = Organization.objects.get(id=ctx.link.organization_id)

    # 1. Реальный долг — суммируем неоплаченные confirmed-продажи.
    # check_customer_credit для клиентов без credit_limit/max_overdue даёт 0
    # (fast-path), что вводит в заблуждение «у вас 0 so'm долг» при наличии
    # реальной дебиторки. Считаем сами.
    unpaid_qs = (
        SaleOrder.objects
        .filter(organization=org, customer=cp, status=SaleOrder.Status.CONFIRMED)
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
    )
    actual_debt = sum(
        (Decimal(o.amount_uzs or 0) - Decimal(o.paid_amount_uzs or 0))
        for o in unpaid_qs
    )

    # 2. Решение блокировки — оставляем check_customer_credit (единая правда
    # с confirm_sale).
    result = check_customer_credit(
        organization=org, customer=cp, new_sale_uzs=Decimal("0"),
    )

    if result.ok:
        lines = [
            "✅ <b>Holat: faol</b>",
            "",
            f"<i>{cp.name}</i>",
            "",
            f"Joriy qarz: <b>{_fmt_money(actual_debt)}</b> so'm",
        ]
        if result.limit_uzs is not None:
            available = result.limit_uzs - actual_debt
            lines.append(
                f"Kredit limiti: {_fmt_money(result.limit_uzs)} so'm"
            )
            lines.append(
                f"Mavjud limit: <b>{_fmt_money(available)}</b> so'm"
            )
        elif actual_debt > 0:
            # Лимит не задан, но долг есть — предупреждаем без блока.
            lines.append("")
            lines.append("ℹ️ Kredit limiti belgilanmagan, lekin qarzdorlik mavjud.")
        lines.append("")
        if actual_debt > 0:
            lines.append(
                "Yangi xaridlarga ruxsat bor, lekin avvalgi qarzni "
                "iloji boricha tezroq to'lash tavsiya etiladi."
            )
        else:
            lines.append("Yangi xaridlarga ruxsat bor.")
    else:
        lines = [
            "🚫 <b>Holat: bloklangan</b>",
            "",
            f"<i>{cp.name}</i>",
            "",
            # actual_debt — посчитан из SaleOrder, не из credit_check fast-path
            f"Joriy qarz: <b>{_fmt_money(actual_debt)}</b> so'm",
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
