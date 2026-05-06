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


def _fmt_dt(dt) -> str:
    """
    Полный человекочитаемый datetime: 06.05.2026 14:32.
    Принимает date / datetime / None. Если None — возвращает прочерк.
    Использует local timezone (TIME_ZONE из settings).
    """
    from datetime import date as _date, datetime as _datetime
    from django.utils import timezone

    if dt is None:
        return "—"
    if isinstance(dt, _datetime):
        if timezone.is_aware(dt):
            dt = timezone.localtime(dt)
        return dt.strftime("%d.%m.%Y %H:%M")
    if isinstance(dt, _date):
        return dt.strftime("%d.%m.%Y")
    return str(dt)


def _fmt_date(d) -> str:
    """Только дата: 06.05.2026."""
    from datetime import date as _date, datetime as _datetime
    from django.utils import timezone

    if d is None:
        return "—"
    if isinstance(d, _datetime):
        if timezone.is_aware(d):
            d = timezone.localtime(d)
        return d.strftime("%d.%m.%Y")
    if isinstance(d, _date):
        return d.strftime("%d.%m.%Y")
    return str(d)


def _module_label(module) -> str:
    """Человекочитаемое имя модуля или '—'."""
    if module is None:
        return "—"
    return getattr(module, "name", None) or getattr(module, "code", "—")


def _cash_label(payment) -> str:
    """«50.02 · Вет аптека Касса» или fallback по каналу."""
    sub = getattr(payment, "cash_subaccount", None)
    if sub is not None:
        return f"{sub.code} · {sub.name}"
    return payment.get_channel_display()


# ─── Закуп (uz) — для админов/head purchases ──────────────────────────────


def fmt_purchase_confirmed(order) -> str:
    """Xarid uchun barcha muhim ma'lumotlar: hujjat, yetkazib beruvchi,
    summa, modul, sana + vaqt o'tkazilgan."""
    debt_block = ""
    try:
        from decimal import Decimal
        paid = Decimal(order.paid_amount_uzs or 0)
        total = Decimal(order.amount_uzs or 0)
        debt = total - paid
        if debt > 0:
            debt_block = f"\n⏳ <b>Qarz biz:</b> {_fmt_money(debt)} so'm"
        elif paid > 0:
            debt_block = "\n✅ <b>To'liq to'langan</b>"
    except Exception:
        pass

    return (
        "🛒 <b>Xarid o'tkazildi</b>\n"
        "\n"
        f"📄 <b>Hujjat:</b> <code>{order.doc_number}</code>\n"
        f"🏢 <b>Yetkazib beruvchi:</b> {order.counterparty.name}\n"
        f"🗂 <b>Modul:</b> {_module_label(order.module)}\n"
        f"💰 <b>Summa:</b> {_fmt_money(order.amount_uzs)} so'm"
        f"{debt_block}\n"
        "\n"
        f"📅 <b>Sana:</b> {_fmt_date(order.date)}\n"
        f"🕐 <b>O'tkazildi:</b> {_fmt_dt(order.updated_at)}"
    )


# ─── Платёж (uz) — для админов модуля ─────────────────────────────────────


def fmt_payment_posted(payment) -> str:
    """
    Полный финансовый отчёт по проведённому платежу:
        - Направление (расход/доход) + тип (поставщик/клиент/опex)
        - Контрагент (если есть)
        - Касса/счёт куда поступило / откуда списано
        - Канал (наличные / банк / Click)
        - Модуль (для скоупа)
        - Сумма + статья расходов (для opex)
        - Дата операции + полное datetime проведения
    """
    if payment.direction == "out":
        icon, header = "💸", "Chiqim — to'lov amalga oshirildi"
    else:
        icon, header = "💰", "Kirim — pul tushdi"

    lines = [f"{icon} <b>{header}</b>", ""]

    # Контрагент
    if payment.counterparty_id:
        lines.append(f"🏢 <b>Kontragent:</b> {payment.counterparty.name}")

    # Тип платежа
    kind_display = payment.get_kind_display()
    lines.append(f"🏷 <b>Turi:</b> {kind_display}")

    # Касса/счёт — критично для понимания «куда деньги»
    lines.append(f"💼 <b>Kassa/hisob:</b> {_cash_label(payment)}")
    lines.append(f"💳 <b>Kanal:</b> {payment.get_channel_display()}")

    # Модуль (если задан) — для модульной аналитики
    if payment.module_id:
        lines.append(f"🗂 <b>Modul:</b> {_module_label(payment.module)}")

    # Статья расходов (для opex)
    if payment.expense_article_id:
        lines.append(f"📁 <b>Modda:</b> {payment.expense_article.name}")

    lines.append("")
    lines.append(f"💰 <b>Summa:</b> <code>{_fmt_money(payment.amount_uzs)}</code> so'm")
    lines.append("")

    # Даты
    lines.append(f"📅 <b>Operatsiya sanasi:</b> {_fmt_date(payment.date)}")
    lines.append(f"🕐 <b>O'tkazildi:</b> {_fmt_dt(payment.updated_at)}")

    # Документ
    lines.append("")
    lines.append(f"📄 <code>{payment.doc_number}</code>")

    return "\n".join(lines)


# ─── Платёж (uz) — для клиента (получил наш платёж к ним или мы получили его) ─


def fmt_payment_received_for_client(payment, order=None) -> str:
    """Mijozga: «sizning to'lovingiz qabul qilindi». Если есть order —
    добавляем номер счёта и остаток долга."""
    lines = [
        "✅ <b>To'lovingiz qabul qilindi!</b>",
        "",
        f"💰 <b>Summa:</b> <code>{_fmt_money(payment.amount_uzs)}</code> so'm",
        f"💳 <b>Kanal:</b> {payment.get_channel_display()}",
        "",
        f"📅 <b>Sana:</b> {_fmt_date(payment.date)}",
        f"🕐 <b>Qabul qilindi:</b> {_fmt_dt(payment.updated_at)}",
    ]
    if order is not None:
        lines.append("")
        lines.append(f"📄 <b>Buyurtma:</b> <code>{order.doc_number}</code>")
        try:
            from decimal import Decimal
            remaining = Decimal(order.amount_uzs or 0) - Decimal(order.paid_amount_uzs or 0)
        except Exception:
            remaining = None
        if remaining is not None:
            if remaining <= 0:
                lines.append("✅ <b>Buyurtma to'liq yopildi.</b>")
            else:
                lines.append(
                    f"📊 <b>Qoldiq qarz:</b> {_fmt_money(remaining)} so'm"
                )
    return "\n".join(lines)


# ─── Долг (uz) — клиенту, ежедневное напоминание ──────────────────────────


def fmt_debt_reminder_uz(sale_order, counterparty) -> str:
    """Mijozga qarzdorlik haqida xabarnoma — escalation tone по delta_days.

    Тон нарастает:
    - до срока (delta>0): мягко
    - в день (delta=0): «Bugun to'lov kuni»
    - просрочка 1-7 дней: твёрдо но вежливо
    - 8-30 дней: серьёзно, упоминаем риск блокировки
    - 30+ дней: жёстко, последнее предупреждение
    Это снижает game-the-system эффект «бот дёргает но ничего не меняется».
    """
    from datetime import date as _date
    from decimal import Decimal

    remaining = Decimal(sale_order.amount_uzs or 0) - Decimal(sale_order.paid_amount_uzs or 0)

    delta = None
    if sale_order.due_date:
        delta = (sale_order.due_date - _date.today()).days

    # Подбор тональности по delta
    if delta is None:
        # Без due_date — generic reminder
        header = f"📢 <b>Eslatma: qarzdorlik mavjud</b>"
        deadline_block = ""
        tone_block = (
            "💳 Iltimos, to'lovni amalga oshiring.\n\n"
            "❓ Savol bo'lsa, biz bilan bog'laning."
        )
    elif delta > 0:
        header = "📢 <b>To'lov muddati yaqinlashmoqda</b>"
        deadline_block = (
            f"⏳ To'lov muddati: <b>{sale_order.due_date}</b> "
            f"({delta} kun qoldi)\n"
        )
        tone_block = "💳 Iltimos, o'z vaqtida to'lang. Rahmat."
    elif delta == 0:
        header = "⚠️ <b>Bugun to'lov kuni!</b>"
        deadline_block = f"📅 Muddati: <b>{sale_order.due_date}</b>\n"
        tone_block = "💳 Iltimos, bugun to'lovni amalga oshiring."
    elif delta >= -7:
        header = f"🚨 <b>{abs(delta)} kun kechikkan</b>"
        deadline_block = f"📅 Muddati edi: {sale_order.due_date}\n"
        tone_block = (
            "💳 Iltimos, qarzni iloji boricha tezroq to'lang.\n"
            "❓ Qiyinchilik bo'lsa — menejer bilan bog'laning."
        )
    elif delta >= -30:
        header = f"🔴 <b>Jiddiy kechikish: {abs(delta)} kun</b>"
        deadline_block = f"📅 Muddati edi: {sale_order.due_date}\n"
        tone_block = (
            "⚠️ <b>Diqqat:</b> Qarzdorlik davom etsa, yangi xaridlar "
            "vaqtincha to'xtatilishi mumkin.\n"
            "💳 Iltimos, bugun-ertaga to'lang yoki menejer bilan "
            "kelishuv tuzing."
        )
    else:
        header = f"🚨🚨 <b>Oxirgi ogohlantirish: {abs(delta)} kun kechikish</b>"
        deadline_block = f"📅 Muddati edi: {sale_order.due_date}\n"
        tone_block = (
            "⛔ Qarzdorlik 30 kundan oshdi. Yangi xaridlar bloklangan.\n"
            "💼 Hisob-kitobni kelishish uchun zudlik bilan menejer "
            "bilan bog'laning."
        )

    return (
        f"{header}\n\n"
        f"<i>{counterparty.name}</i>\n"
        f"📄 Buyurtma: <code>{sale_order.doc_number}</code>\n"
        f"💰 Qarz: <b>{_fmt_money(remaining)} so'm</b>\n"
        f"📅 Buyurtma sanasi: {sale_order.date}\n"
        f"{deadline_block}\n"
        f"{tone_block}"
    )


def fmt_promise_broken_uz(sale_order, communication) -> str:
    """Mijozga: «kecha to'lashga va'da bergan edingiz, hali to'lov yo'q»."""
    from decimal import Decimal

    remaining = Decimal(sale_order.amount_uzs or 0) - Decimal(sale_order.paid_amount_uzs or 0)
    return (
        f"📢 <b>Va'dangiz haqida</b>\n\n"
        f"<i>{sale_order.customer.name}</i>\n\n"
        f"Siz <b>{communication.promised_pay_date}</b> kuni to'lashga "
        f"va'da bergan edingiz, biroq to'lov hali kelmadi.\n\n"
        f"📄 Buyurtma: <code>{sale_order.doc_number}</code>\n"
        f"💰 Qarz: <b>{_fmt_money(remaining)} so'm</b>\n\n"
        f"💳 Iltimos, qarzni to'lang yoki yangi muddat haqida menejerga "
        f"xabar bering."
    )


def fmt_head_brief_uz(org, module_code: str) -> str | None:
    """Утренний brief head'у модуля: за вчера sotuv / xarid / cash-снимок.

    Возвращает None если по модулю за вчера ничего не происходило —
    тогда не шлём (без шума).
    """
    from datetime import date as _date, timedelta
    from decimal import Decimal
    from django.db.models import Q, Sum
    from apps.modules.models import Module
    from apps.purchases.models import PurchaseOrder
    from apps.sales.models import SaleOrder

    try:
        module = Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        return None

    yesterday = _date.today() - timedelta(days=1)

    # Sales вчера: distinct orders с item этого модуля
    so_qs = SaleOrder.objects.filter(
        organization=org, status=SaleOrder.Status.CONFIRMED,
        date=yesterday,
    )
    if module_code == "feed":
        so_qs = so_qs.filter(
            Q(items__feed_batch__isnull=False)
            | Q(items__feed_bag_lot__isnull=False)
        )
    elif module_code == "vet":
        so_qs = so_qs.filter(
            Q(items__vet_stock_batch__isnull=False)
            | Q(items__vet_accessory__isnull=False)
        )
    elif module_code in ("matochnik", "incubation", "feedlot", "slaughter"):
        so_qs = so_qs.filter(items__batch__current_module__code=module_code)
    else:
        so_qs = so_qs.none()

    so_agg = so_qs.distinct().aggregate(
        n=_count_zero(),
        s=Sum("amount_uzs"),
        p=Sum("paid_amount_uzs"),
    )
    sales_count = so_agg["n"] or 0
    sales_invoiced = Decimal(so_agg["s"] or 0)
    sales_paid = Decimal(so_agg["p"] or 0)

    po_agg = PurchaseOrder.objects.filter(
        organization=org, module=module,
        status=PurchaseOrder.Status.CONFIRMED,
        date=yesterday,
    ).aggregate(
        n=_count_zero(),
        s=Sum("amount_uzs"),
        p=Sum("paid_amount_uzs"),
    )
    purch_count = po_agg["n"] or 0
    purch_invoiced = Decimal(po_agg["s"] or 0)
    purch_paid = Decimal(po_agg["p"] or 0)

    # Если за вчера вообще ничего — пустой brief не шлём
    if sales_count == 0 and purch_count == 0:
        return None

    label = MODULE_LABEL_BRIEF.get(module_code, module_code)
    lines = [
        f"☀️ <b>Tongi brief — {label}</b>",
        f"<i>Kechagi kun: {yesterday}</i>",
        "",
    ]
    if sales_count > 0:
        debt = sales_invoiced - sales_paid
        lines.append(
            f"📤 Sotuv: <b>{sales_count}</b> ta · "
            f"{_fmt_money(sales_invoiced)} so'm"
        )
        lines.append(
            f"   ↳ to'landi: {_fmt_money(sales_paid)} · "
            f"qarz: <b>{_fmt_money(debt)}</b>"
        )
    if purch_count > 0:
        debt = purch_invoiced - purch_paid
        lines.append(
            f"📥 Xarid: <b>{purch_count}</b> ta · "
            f"{_fmt_money(purch_invoiced)} so'm"
        )
        lines.append(
            f"   ↳ to'landi: {_fmt_money(purch_paid)} · "
            f"qarz biz: <b>{_fmt_money(debt)}</b>"
        )

    return "\n".join(lines)


# Узбекские лейблы для head-brief (сжато — в pushe место экономим).
MODULE_LABEL_BRIEF = {
    "matochnik":  "Naslchilik",
    "incubation": "Inkubatsiya",
    "feedlot":    "Bo'rdoqi",
    "slaughter":  "So'yishxona",
    "feed":       "Yem",
    "vet":        "Veterinariya",
}


def _count_zero():
    """`Count('id')` хелпер чтобы не таскать import повсюду."""
    from django.db.models import Count
    return Count("id")


def fmt_cashflow_alert_uz(negatives: list, total_uzs) -> str:
    """Alert о минусе на кассах/счетах. negatives = [(label, balance), …]."""
    from decimal import Decimal

    lines = [
        "🚨 <b>Diqqat: kassada manfiy qoldiq!</b>",
        "",
    ]
    for label, bal in negatives:
        lines.append(
            f"  🔴 {label}: <b>−{_fmt_money(abs(Decimal(str(bal))))}</b> so'm"
        )
    total = Decimal(str(total_uzs))
    if total < 0:
        lines.append("")
        lines.append(f"<b>Jami:</b> <b>−{_fmt_money(abs(total))}</b> so'm")
    lines.append("")
    lines.append(
        "⚠️ Tekshiring: dastlabki qoldiqlar to'g'ri sozlanganmi yoki "
        "haqiqatda overdraft bormi."
    )
    return "\n".join(lines)


def fmt_stale_payment_alert_uz(stale_orders: list, threshold_days: int) -> str:
    """Alert sales-админу: продажи без касания > threshold_days."""
    lines = [
        f"📞 <b>Mijozlar bilan ishlash kerak</b>",
        f"<i>{threshold_days} kundan ortiq qarzdorlar bilan aloqa yo'q</i>",
        "",
        f"Jami: <b>{len(stale_orders)}</b> ta hujjat",
        "",
    ]
    for o in stale_orders[:10]:
        from decimal import Decimal
        debt = Decimal(o.amount_uzs or 0) - Decimal(o.paid_amount_uzs or 0)
        cust = o.customer.name if o.customer_id else "—"
        lines.append(
            f"• <b>{cust}</b>\n"
            f"   <code>{o.doc_number}</code> · qarz "
            f"<b>{_fmt_money(debt)}</b> so'm"
        )
    if len(stale_orders) > 10:
        lines.append(f"… va yana {len(stale_orders) - 10} ta")
    lines.append("")
    lines.append("💼 Mijozlar bilan bog'lanib, va'da olib qo'ying.")
    return "\n".join(lines)


def fmt_low_stock_alert_uz(alerts: list) -> str:
    """Alert head feed'a: партии корма закончатся через <3 дня."""
    lines = [
        "📉 <b>Yem zaxiralari tugayapti!</b>",
        "<i>Joriy iste'mol bo'yicha 3 kundan kam qoldi</i>",
        "",
    ]
    for a in alerts[:10]:
        lines.append(
            f"• <b>{a['label']}</b>\n"
            f"   Qoldiq: {a['remaining']} · "
            f"o'rtacha: {a['avg_daily']} · "
            f"<b>{a['days_left']} kun</b> qoldi"
        )
    if len(alerts) > 10:
        lines.append(f"… va yana {len(alerts) - 10} ta")
    lines.append("")
    lines.append("🌾 Yangi zamesni rejalashtiring yoki xom-ashyo xarid qiling.")
    return "\n".join(lines)


def fmt_weekly_summary_uz(org) -> str | None:
    """Понедельник 07:00 — обзор прошлой недели для admin/reports."""
    from datetime import date as _date, timedelta
    from decimal import Decimal
    from django.db.models import Count, Sum
    from apps.purchases.models import PurchaseOrder
    from apps.sales.models import SaleOrder

    today = _date.today()
    week_end = today - timedelta(days=1)
    week_start = today - timedelta(days=7)

    so_agg = SaleOrder.objects.filter(
        organization=org, status=SaleOrder.Status.CONFIRMED,
        date__gte=week_start, date__lte=week_end,
    ).aggregate(
        n=Count("id"),
        s=Sum("amount_uzs"),
        p=Sum("paid_amount_uzs"),
    )
    sales_n = so_agg["n"] or 0
    sales_total = Decimal(so_agg["s"] or 0)
    sales_paid = Decimal(so_agg["p"] or 0)

    po_agg = PurchaseOrder.objects.filter(
        organization=org, status=PurchaseOrder.Status.CONFIRMED,
        date__gte=week_start, date__lte=week_end,
    ).aggregate(
        n=Count("id"),
        s=Sum("amount_uzs"),
        p=Sum("paid_amount_uzs"),
    )
    purch_n = po_agg["n"] or 0
    purch_total = Decimal(po_agg["s"] or 0)
    purch_paid = Decimal(po_agg["p"] or 0)

    if sales_n == 0 and purch_n == 0:
        return None  # пустая неделя — не шумим

    sales_pct = (
        (sales_paid / sales_total * 100) if sales_total > 0 else Decimal("0")
    )
    lines = [
        "📊 <b>Haftalik hisobot</b>",
        f"<i>{week_start} — {week_end}</i>",
        "",
        f"📤 Sotuvlar: <b>{sales_n}</b> ta · "
        f"<b>{_fmt_money(sales_total)}</b> so'm",
        f"  ↳ to'langan: {_fmt_money(sales_paid)} ({sales_pct:.0f}%)",
        f"  ↳ qarz:      <b>{_fmt_money(sales_total - sales_paid)}</b> so'm",
        "",
        f"📥 Xaridlar: <b>{purch_n}</b> ta · "
        f"{_fmt_money(purch_total)} so'm",
        f"  ↳ to'langan: {_fmt_money(purch_paid)}",
        f"  ↳ qarz biz:  {_fmt_money(purch_total - purch_paid)}",
        "",
        "Yangi haftaga sog'-omon yetib bordingiz! 💼",
    ]
    return "\n".join(lines)


def fmt_pre_block_warning_uz(counterparty, credit_result, ratio) -> str:
    """Mijozga: «вы близко к лимиту, ещё немного и блок»."""
    from decimal import Decimal

    debt = Decimal(credit_result.current_debt_uzs)
    limit = Decimal(credit_result.limit_uzs or 0)
    remaining_capacity = limit - debt
    pct = int(float(ratio) * 100)

    return (
        f"⚠️ <b>Diqqat: kredit limitiga yaqinlashmoqda</b>\n\n"
        f"<i>{counterparty.name}</i>\n\n"
        f"📊 Joriy qarz: <b>{_fmt_money(debt)} so'm</b>\n"
        f"📈 Limitdan ishlatilgan: <b>{pct}%</b>\n"
        f"💼 Yangi xaridlarga qoldi: <b>{_fmt_money(remaining_capacity)} so'm</b>\n\n"
        f"💳 Limit oshgan zahoti yangi xaridlar to'xtatiladi. "
        f"Iloji boricha qarzni to'lang."
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
    """Хедер: «Sotuv qaydlandi · mahsulot jo'natildi» — чтобы не путали с
    приходом денег. Явно показываем qarz и срок оплаты."""
    from decimal import Decimal
    items_count = order.items.count() if hasattr(order, "items") else 0
    paid = Decimal(order.paid_amount_uzs or 0)
    total = Decimal(order.amount_uzs or 0)
    debt = total - paid

    lines = [
        "📋 <b>Sotuv qaydlandi · mahsulot jo'natildi</b>",
        "<i>Pul hali kelgani yo'q — alohida bildirish bo'ladi</i>",
        "",
        f"📄 <b>Hujjat:</b> <code>{order.doc_number}</code>",
        f"👤 <b>Mijoz:</b> {order.customer.name}",
        f"🗂 <b>Modul:</b> {_module_label(order.module)}",
        f"📦 <b>Pozitsiyalar:</b> {items_count}",
        "",
        f"💰 <b>Summa:</b> <code>{_fmt_money(total)}</code> so'm",
    ]
    if debt > 0:
        lines.append(f"⏳ <b>To'lanmagan:</b> {_fmt_money(debt)} so'm")
    elif paid > 0 and debt <= 0:
        lines.append("✅ <b>To'lov to'liq qabul qilingan</b>")

    lines.append("")
    lines.append(f"📅 <b>Sana:</b> {_fmt_date(order.date)}")
    lines.append(f"🕐 <b>O'tkazildi:</b> {_fmt_dt(order.updated_at)}")
    if order.due_date and debt > 0:
        lines.append(f"📆 <b>To'lov muddati:</b> {_fmt_date(order.due_date)}")

    return "\n".join(lines)


# ─── Продажа (uz) — для клиента ──────────────────────────────────────────


def fmt_sale_confirmed_for_client(order) -> str:
    """Mijozga: «sizning buyurtmangiz rasmiylashtirildi»."""
    from decimal import Decimal
    items_count = order.items.count() if hasattr(order, "items") else 0
    paid = Decimal(order.paid_amount_uzs or 0)
    total = Decimal(order.amount_uzs or 0)
    debt = total - paid

    lines = [
        "📦 <b>Buyurtma rasmiylashtirildi</b>",
        f"<i>{order.customer.name}</i>",
        "",
        f"📄 <b>Hujjat:</b> <code>{order.doc_number}</code>",
        f"📦 <b>Pozitsiyalar:</b> {items_count}",
        f"💰 <b>Summa:</b> <code>{_fmt_money(total)}</code> so'm",
    ]
    if debt > 0:
        lines.append(f"💸 <b>Sizning qarzingiz:</b> {_fmt_money(debt)} so'm")

    lines.append("")
    lines.append(f"📅 <b>Sana:</b> {_fmt_date(order.date)}")
    lines.append(f"🕐 <b>Qabul qilindi:</b> {_fmt_dt(order.updated_at)}")
    if order.due_date and debt > 0:
        lines.append(f"📆 <b>To'lov muddati:</b> {_fmt_date(order.due_date)}")

    return "\n".join(lines)


# ─── Per-module sale notifications (uz) ──────────────────────────────────


def fmt_sale_for_feed_module(order, items: list) -> str:
    """Korm modul boshlig'iga: nima sotildi (jo'natildi, pul keyinroq)."""
    from decimal import Decimal
    paid = Decimal(order.paid_amount_uzs or 0)
    total = Decimal(order.amount_uzs or 0)
    debt = total - paid
    lines = [
        "🌾 <b>Yem-xashak jo'natildi</b>",
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
    if debt > 0:
        lines.append(f"\n⏳ Qarz: <b>{_fmt_money(debt)} so'm</b> (pul kelmagan)")
    elif paid > 0:
        lines.append(f"\n✅ To'lov to'liq qabul qilingan: {_fmt_money(paid)} so'm")
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
