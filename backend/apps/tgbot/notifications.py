from __future__ import annotations


def fmt_purchase_confirmed(order) -> str:
    return (
        f"🛒 <b>Закуп проведён</b>\n"
        f"📄 Документ: <code>{order.doc_number}</code>\n"
        f"🏢 Поставщик: {order.counterparty.name}\n"
        f"💰 Сумма: <b>{float(order.amount_uzs):,.0f} сум</b>\n"
        f"📅 Дата: {order.date}"
    )


def fmt_payment_posted(payment) -> str:
    if payment.direction == "out":
        icon, direction = "💸", "Выплата поставщику"
    else:
        icon, direction = "💰", "Поступление от клиента"
    counterparty_line = ""
    if payment.counterparty:
        counterparty_line = f"🏢 Контрагент: {payment.counterparty.name}\n"
    return (
        f"{icon} <b>{direction}</b>\n"
        f"{counterparty_line}"
        f"💳 Канал: {payment.get_channel_display()}\n"
        f"💰 Сумма: <b>{float(payment.amount_uzs):,.0f} сум</b>\n"
        f"📅 Дата: {payment.date}"
    )


def fmt_debt_reminder_uz(sale_order, counterparty) -> str:
    remaining = float(sale_order.amount_uzs or 0) - float(sale_order.paid_amount_uzs or 0)
    return (
        f"📢 <b>Hurmatli {counterparty.name}!</b>\n\n"
        f"Sizda <code>{sale_order.doc_number}</code> raqamli buyurtma bo'yicha\n"
        f"<b>{remaining:,.0f} so'm</b> qarzdorlik mavjud.\n\n"
        f"📅 Buyurtma sanasi: {sale_order.date}\n"
        f"💳 Iltimos, to'lovni o'z vaqtida amalga oshiring.\n\n"
        f"❓ Savol bo'lsa, biz bilan bog'laning."
    )


def fmt_report(kpis: dict) -> str:
    period = kpis.get("period", {})
    return (
        f"📊 <b>Отчёт за период</b>\n"
        f"📅 {period.get('from', '?')} — {period.get('to', '?')}\n\n"
        f"💰 Выручка: <b>{_fmt(kpis.get('sales_revenue_uzs'))} сум</b>\n"
        f"🛒 Закупы: <b>{_fmt(kpis.get('purchases_confirmed_uzs'))} сум</b>\n"
        f"📈 Маржа: <b>{_fmt(kpis.get('sales_margin_uzs'))} сум</b>\n\n"
        f"👥 Дебиторка: {_fmt(kpis.get('debtor_balance_uzs'))} сум\n"
        f"🏦 Кредиторка: {_fmt(kpis.get('creditor_balance_uzs'))} сум\n\n"
        f"📦 Активных партий: {kpis.get('active_batches', 0)}\n"
        f"🔄 Передач ожидает: {kpis.get('transfers_pending', 0)}"
    )


def fmt_stock(cash: dict) -> str:
    lines = ["💳 <b>Остатки по каналам</b>\n"]
    icons = {"cash": "💵", "transfer": "🏦", "click": "📱", "other": "🔹"}
    for key, val in cash.items():
        if key == "_total_uzs":
            continue
        icon = icons.get(key, "•")
        balance = float(val.get("balance_uzs", 0))
        label = val.get("label", key)
        lines.append(f"{icon} {label}: <b>{balance:,.0f} сум</b>")
    total = float(cash.get("_total_uzs", 0))
    lines.append(f"\n💰 <b>Итого: {total:,.0f} сум</b>")
    return "\n".join(lines)


def fmt_production(prod: dict) -> str:
    return (
        f"🐔 <b>Производство сейчас</b>\n\n"
        f"🥚 Маточник (голов): <b>{prod.get('matochnik_heads', 0):,}</b>\n"
        f"🐣 Инкубация (партий): <b>{prod.get('incubation_runs', 0)}</b> "
        f"/ яиц: <b>{prod.get('incubation_eggs_loaded', 0):,}</b>\n"
        f"🍗 Откорм (голов): <b>{prod.get('feedlot_heads', 0):,}</b>"
    )


def fmt_cashflow(points: list[dict], days: int) -> str:
    if not points:
        return "Нет данных по кэш-флоу."
    total_in = sum(float(p["in_uzs"]) for p in points)
    total_out = sum(float(p["out_uzs"]) for p in points)
    net = total_in - total_out
    net_icon = "📈" if net >= 0 else "📉"
    lines = [f"📊 <b>Кэш-флоу за {days} дней</b>\n"]
    for p in points[-7:]:  # последние 7 строк
        in_v = float(p["in_uzs"])
        out_v = float(p["out_uzs"])
        if in_v == 0 and out_v == 0:
            continue
        lines.append(
            f"  {p['date']}: ▲{in_v:,.0f} / ▼{out_v:,.0f}"
        )
    lines.append(f"\n💰 Приход: <b>{total_in:,.0f} сум</b>")
    lines.append(f"💸 Расход: <b>{total_out:,.0f} сум</b>")
    lines.append(f"{net_icon} Сальдо: <b>{net:,.0f} сум</b>")
    return "\n".join(lines)


def _fmt(val) -> str:
    try:
        return f"{float(val):,.0f}"
    except (TypeError, ValueError):
        return "—"
