"""
TG-форматтеры уведомлений. Все клиент- и сотрудник-facing сообщения — на
узбекском (по требованию бизнеса). Внутренние fmt_qty/_fmt — без локали.

Аудитории:
  - admin/head — сотрудники организации, привязанные через user-TgLink
  - client     — контрагент (counterparty), привязанный через TgLink

Каждое событие может слаться нескольким аудиториям с разным текстом
(см. orchestration.notify_payment_event).
"""
from __future__ import annotations


# ─── helpers ──────────────────────────────────────────────────────────────


def _fmt_qty(value) -> str:
    """Аккуратное число: без хвостовых нулей."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    if f == int(f):
        return f"{int(f):,}".replace(",", " ")
    return f"{f:,.3f}".rstrip("0").rstrip(".")


def _fmt_money(value) -> str:
    """Сумма с пробелами как разделители тысяч."""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return "—"


# ─── Закуп (uz) — для админов/head purchases ──────────────────────────────


def fmt_purchase_confirmed(order) -> str:
    return (
        f"🛒 <b>Xarid o'tkazildi</b>\n"
        f"📄 Hujjat: <code>{order.doc_number}</code>\n"
        f"🏢 Yetkazib beruvchi: {order.counterparty.name}\n"
        f"💰 Summa: <b>{_fmt_money(order.amount_uzs)} so'm</b>\n"
        f"📅 Sana: {order.date}"
    )


# ─── Платёж (uz) — для админов модуля ─────────────────────────────────────


def fmt_payment_posted(payment) -> str:
    if payment.direction == "out":
        icon, direction = "💸", "Yetkazib beruvchiga to'lov"
    else:
        icon, direction = "💰", "Mijozdan tushum"
    counterparty_line = ""
    if payment.counterparty:
        counterparty_line = f"🏢 Kontragent: {payment.counterparty.name}\n"
    return (
        f"{icon} <b>{direction}</b>\n"
        f"{counterparty_line}"
        f"💳 Kanal: {payment.get_channel_display()}\n"
        f"💰 Summa: <b>{_fmt_money(payment.amount_uzs)} so'm</b>\n"
        f"📅 Sana: {payment.date}"
    )


# ─── Платёж (uz) — для клиента (получил наш платёж к ним или мы получили его) ─


def fmt_payment_received_for_client(payment, order=None) -> str:
    """Mijozga: «sizning to'lovingiz qabul qilindi». Если есть order —
    добавляем номер счёта и остаток долга."""
    lines = [
        "✅ <b>To'lovingiz qabul qilindi!</b>",
        f"💰 Summa: <b>{_fmt_money(payment.amount_uzs)} so'm</b>",
        f"💳 Kanal: {payment.get_channel_display()}",
        f"📅 Sana: {payment.date}",
    ]
    if order is not None:
        lines.append("")
        lines.append(f"📄 Buyurtma: <code>{order.doc_number}</code>")
        try:
            from decimal import Decimal
            remaining = Decimal(order.amount_uzs or 0) - Decimal(order.paid_amount_uzs or 0)
        except Exception:
            remaining = None
        if remaining is not None:
            if remaining <= 0:
                lines.append("✨ <b>Buyurtma to'liq to'langan, rahmat!</b>")
            else:
                lines.append(
                    f"📊 Qoldiq qarz: <b>{_fmt_money(remaining)} so'm</b>"
                )
    return "\n".join(lines)


# ─── Долг (uz) — клиенту, ежедневное напоминание ──────────────────────────


def fmt_debt_reminder_uz(sale_order, counterparty) -> str:
    """Mijozga qarzdorlik haqida xabarnoma."""
    from datetime import date as _date
    from decimal import Decimal

    remaining = Decimal(sale_order.amount_uzs or 0) - Decimal(sale_order.paid_amount_uzs or 0)

    deadline_block = ""
    if sale_order.due_date:
        delta = (sale_order.due_date - _date.today()).days
        if delta > 0:
            deadline_block = (
                f"⏳ To'lov muddati: <b>{sale_order.due_date}</b> "
                f"({delta} kun qoldi)\n"
            )
        elif delta == 0:
            deadline_block = f"⚠️ <b>Bugun to'lov kuni!</b> ({sale_order.due_date})\n"
        else:
            deadline_block = (
                f"🚨 <b>{abs(delta)} kun kechikkan!</b> "
                f"(muddati: {sale_order.due_date})\n"
            )

    return (
        f"📢 <b>Hurmatli {counterparty.name}!</b>\n\n"
        f"Sizda <code>{sale_order.doc_number}</code> raqamli buyurtma bo'yicha\n"
        f"<b>{_fmt_money(remaining)} so'm</b> qarzdorlik mavjud.\n\n"
        f"📅 Buyurtma sanasi: {sale_order.date}\n"
        f"{deadline_block}"
        f"💳 Iltimos, to'lovni o'z vaqtida amalga oshiring.\n\n"
        f"❓ Savol bo'lsa, biz bilan bog'laning."
    )


# ─── Отчёт (uz) — для бот-команды ──────────────────────────────────────────


def fmt_report(kpis: dict) -> str:
    period = kpis.get("period", {})
    return (
        f"📊 <b>Davr hisoboti</b>\n"
        f"📅 {period.get('from', '?')} — {period.get('to', '?')}\n\n"
        f"💰 Tushum: <b>{_fmt(kpis.get('sales_revenue_uzs'))} so'm</b>\n"
        f"🛒 Xaridlar: <b>{_fmt(kpis.get('purchases_confirmed_uzs'))} so'm</b>\n"
        f"📈 Marja: <b>{_fmt(kpis.get('sales_margin_uzs'))} so'm</b>\n\n"
        f"👥 Debitorlar qarzi: {_fmt(kpis.get('debtor_balance_uzs'))} so'm\n"
        f"🏦 Kreditorlar qarzi: {_fmt(kpis.get('creditor_balance_uzs'))} so'm\n\n"
        f"📦 Faol partiyalar: {kpis.get('active_batches', 0)}\n"
        f"🔄 Kutilayotgan o'tkazmalar: {kpis.get('transfers_pending', 0)}"
    )


def fmt_stock(cash: dict) -> str:
    lines = ["💳 <b>Kanallar bo'yicha qoldiqlar</b>\n"]
    icons = {"cash": "💵", "transfer": "🏦", "click": "📱", "other": "🔹"}
    for key, val in cash.items():
        if key == "_total_uzs":
            continue
        icon = icons.get(key, "•")
        balance = float(val.get("balance_uzs", 0))
        label = val.get("label", key)
        lines.append(f"{icon} {label}: <b>{_fmt_money(balance)} so'm</b>")
    total = float(cash.get("_total_uzs", 0))
    lines.append(f"\n💰 <b>Jami: {_fmt_money(total)} so'm</b>")
    return "\n".join(lines)


def fmt_production(prod: dict) -> str:
    return (
        f"🐔 <b>Hozirgi ishlab chiqarish</b>\n\n"
        f"🥚 Onalik (bosh): <b>{prod.get('matochnik_heads', 0):,}</b>\n"
        f"🐣 Inkubatsiya (partiyalar): <b>{prod.get('incubation_runs', 0)}</b> "
        f"/ tuxum: <b>{prod.get('incubation_eggs_loaded', 0):,}</b>\n"
        f"🍗 Bo'rdoqi (bosh): <b>{prod.get('feedlot_heads', 0):,}</b>"
    )


def fmt_cashflow(points: list[dict], days: int) -> str:
    if not points:
        return "Cash-flow ma'lumotlari yo'q."
    total_in = sum(float(p["in_uzs"]) for p in points)
    total_out = sum(float(p["out_uzs"]) for p in points)
    net = total_in - total_out
    net_icon = "📈" if net >= 0 else "📉"
    lines = [f"📊 <b>{days} kunlik cash-flow</b>\n"]
    for p in points[-7:]:
        in_v = float(p["in_uzs"])
        out_v = float(p["out_uzs"])
        if in_v == 0 and out_v == 0:
            continue
        lines.append(
            f"  {p['date']}: ▲{_fmt_money(in_v)} / ▼{_fmt_money(out_v)}"
        )
    lines.append(f"\n💰 Tushum: <b>{_fmt_money(total_in)} so'm</b>")
    lines.append(f"💸 Xarajat: <b>{_fmt_money(total_out)} so'm</b>")
    lines.append(f"{net_icon} Saldo: <b>{_fmt_money(net)} so'm</b>")
    return "\n".join(lines)


def _fmt(val) -> str:
    try:
        return _fmt_money(val)
    except (TypeError, ValueError):
        return "—"


# ─── Продажа (uz) — для админов sales (общая сводка) ──────────────────────


def fmt_sale_confirmed(order) -> str:
    items_count = order.items.count() if hasattr(order, "items") else 0
    due_block = ""
    if order.due_date:
        due_block = f"⏳ To'lov muddati: {order.due_date}\n"
    return (
        f"💼 <b>Sotuv o'tkazildi</b>\n"
        f"📄 Hujjat: <code>{order.doc_number}</code>\n"
        f"👤 Mijoz: {order.customer.name}\n"
        f"📦 Pozitsiyalar: {items_count}\n"
        f"💰 Summa: <b>{_fmt_money(order.amount_uzs)} so'm</b>\n"
        f"📅 Sana: {order.date}\n"
        f"{due_block}"
    )


# ─── Продажа (uz) — для клиента ──────────────────────────────────────────


def fmt_sale_confirmed_for_client(order) -> str:
    """Mijozga: «sizning buyurtmangiz rasmiylashtirildi»."""
    items_count = order.items.count() if hasattr(order, "items") else 0
    due_block = ""
    if order.due_date:
        due_block = f"⏳ To'lov muddati: <b>{order.due_date}</b>\n"
    return (
        f"📦 <b>Hurmatli {order.customer.name}!</b>\n\n"
        f"Sizning buyurtmangiz rasmiylashtirildi.\n\n"
        f"📄 Buyurtma: <code>{order.doc_number}</code>\n"
        f"📦 Pozitsiyalar: {items_count}\n"
        f"💰 Summa: <b>{_fmt_money(order.amount_uzs)} so'm</b>\n"
        f"📅 Sana: {order.date}\n"
        f"{due_block}\n"
        f"Rahmat! ❤️"
    )


# ─── Per-module sale notifications (uz) ──────────────────────────────────


def fmt_sale_for_feed_module(order, items: list) -> str:
    """Korm modul boshlig'iga: nima sotildi."""
    lines = [
        "🌾 <b>Yem-xashak sotildi</b>",
        f"📄 {order.doc_number} · {order.date}",
        f"👤 {order.customer.name}",
        "",
    ]
    for it in items:
        if it.feed_bag_lot_id:
            bl = it.feed_bag_lot
            qty = int(float(it.quantity))
            lines.append(
                f"• <code>{bl.doc_number}</code> · {bl.recipe_version.recipe.code} ·"
                f" {qty} qop × {_fmt_qty(bl.bag_weight_kg)} kg"
                f" → {_fmt_money(it.line_total_uzs)} so'm"
            )
        elif it.feed_batch_id:
            fb = it.feed_batch
            recipe = fb.recipe_version.recipe.code if fb.recipe_version_id else "—"
            lines.append(
                f"• <code>{fb.doc_number}</code> · {recipe} ·"
                f" {_fmt_qty(it.quantity)} kg"
                f" → {_fmt_money(it.line_total_uzs)} so'm"
            )
    return "\n".join(lines)


def fmt_sale_for_vet_module(order, items: list) -> str:
    """Vet modul boshlig'iga: qanday vet-tovar sotildi."""
    lines = [
        "💊 <b>Vet-tovar sotildi</b>",
        f"📄 {order.doc_number} · {order.date}",
        f"👤 {order.customer.name}",
        "",
    ]
    for it in items:
        if it.vet_stock_batch_id:
            vsb = it.vet_stock_batch
            drug = vsb.drug.nomenclature.name if vsb.drug.nomenclature_id else vsb.lot_number
            lines.append(
                f"• <code>{vsb.doc_number}</code> · {drug} ·"
                f" {_fmt_qty(it.quantity)} {vsb.unit.code if vsb.unit_id else 'dona'}"
                f" → {_fmt_money(it.line_total_uzs)} so'm"
            )
        elif it.vet_accessory_id:
            va = it.vet_accessory
            name = va.nomenclature.name if va.nomenclature_id else va.nomenclature.sku
            lines.append(
                f"• {name} · {_fmt_qty(it.quantity)} dona"
                f" → {_fmt_money(it.line_total_uzs)} so'm"
            )
    return "\n".join(lines)


def fmt_sale_for_generic_module(order, items: list, module_label: str) -> str:
    """Slaughter/feedlot/matochnik/incubation — обычные batches."""
    lines = [
        f"📦 <b>«{module_label}» dan sotildi</b>",
        f"📄 {order.doc_number} · {order.date}",
        f"👤 {order.customer.name}",
        "",
    ]
    for it in items:
        if it.batch_id:
            b = it.batch
            sku = b.nomenclature.sku if b.nomenclature_id else "—"
            lines.append(
                f"• <code>{b.doc_number}</code> · {sku} ·"
                f" {_fmt_qty(it.quantity)} {b.unit.code if b.unit_id else 'dona'}"
                f" → {_fmt_money(it.line_total_uzs)} so'm"
            )
    return "\n".join(lines)
