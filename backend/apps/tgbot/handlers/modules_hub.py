"""
«Modullar» (бывшее «Производство») — список активных модулей организации
+ per-module hub: касса/банк, склады, партии, KPI в одном экране.

Юзеры видят только модули к которым у них доступ ≥ r (RBAC scope).
Owner видит все enabled-модули организации.

Архитектура:
- home:modules → список модулей кнопками (mod:<code>)
- mod:<code>   → hub этого модуля (cash + warehouses + batches + KPI)
- mod:<code>:cash → детальный cash-flow модуля (если есть привязка JE.module)
- mod:<code>:wh   → склады модуля с остатками
- mod:<code>:lots → партии модуля (FeedBatch / Batch / VetStockBatch)
"""
from __future__ import annotations

import logging
from decimal import Decimal

from ..bot import edit_message_text, send_message
from ..dispatcher import HandlerCtx, command, on_callback
from ..keyboards import kb
from ..services.menu_scope import is_owner, user_module_levels


logger = logging.getLogger(__name__)


# Модули которые показываем в «Modullar» (исключаем системные ledger/admin/
# core/reports — они есть в других разделах).
PRODUCTION_MODULE_CODES = [
    "matochnik", "incubation", "feedlot", "slaughter",
    "feed", "vet", "stock",
]

# Чистые узбекские названия модулей (бизнес-стандарт, без сленга).
MODULE_LABELS_UZ = {
    "matochnik":  "🐔 Naslchilik",          # племенное стадо
    "incubation": "🥚 Inkubatsiya",
    "feedlot":    "🍗 Bo'rdoqi fabrikasi",  # фабрика откорма
    "slaughter":  "🔪 So'yishxona",         # цех убоя
    "feed":       "🌾 Yem ishlab chiqarish",
    "vet":        "💊 Veterinariya",
    "stock":      "📦 Ombor xo'jaligi",
    "sales":      "💼 Sotuvlar",
    "purchases":  "🛒 Xaridlar",
    "ledger":     "📒 Buxgalteriya",
    "reports":    "📊 Hisobotlar",
    "admin":      "⚙️ Boshqaruv",
}


def _label(code: str) -> str:
    return MODULE_LABELS_UZ.get(code, code)


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


# ─── render «Modullar» (callback `home:modules`) ─────────────────────────


def render_modules_section(ctx: HandlerCtx) -> None:
    """Список активных модулей организации с RBAC-фильтрацией."""
    from apps.common.permissions import level_satisfies
    from apps.modules.models import OrganizationModule

    org = ctx.org()
    levels = user_module_levels(ctx.link)
    owner = is_owner(levels)

    enabled_codes = set(
        OrganizationModule.objects
        .filter(organization=org, is_enabled=True)
        .values_list("module__code", flat=True)
    )

    visible = [
        c for c in PRODUCTION_MODULE_CODES
        if c in enabled_codes
        and (owner or level_satisfies(levels.get(c, "none"), "r"))
    ]

    if not visible:
        text = (
            "🐔 <b>Modullar</b>\n\n"
            "Sizda hech qanday faol modulga ruxsat yo'q."
        )
        _send_or_edit(ctx, text, kb([("← Orqaga", "home")], cols=1))
        return

    text = (
        "🐔 <b>Modullar</b>\n\n"
        f"Faol modullar ({len(visible)}). To'liq ma'lumotni "
        f"ko'rish uchun modul tanlang:"
    )
    buttons = [(_label(c), f"mod:{c}") for c in visible]
    buttons.append(("← Orqaga", "home"))
    _send_or_edit(ctx, text, kb(buttons, cols=2))


# ─── per-module hub (callback `mod:<code>`) ──────────────────────────────


@on_callback("mod")
def handle_module_hub_callback(ctx: HandlerCtx) -> None:
    if not ctx.args:
        return
    code = ctx.args[0]
    if code not in PRODUCTION_MODULE_CODES:
        send_message(ctx.chat_id, f"❌ Noma'lum modul: {code}")
        return

    # RBAC-gate
    from apps.common.permissions import level_satisfies
    levels = user_module_levels(ctx.link)
    if not (is_owner(levels) or level_satisfies(levels.get(code, "none"), "r")):
        send_message(ctx.chat_id, f"⛔ Modulga ruxsat yo'q: {_label(code)}")
        return

    # Подразделы: mod:<code>:cash / wh / lots — TODO future drill-downs.
    # Сейчас один экран — hub.
    _render_module_hub(ctx, module_code=code)


def _render_module_hub(ctx: HandlerCtx, *, module_code: str) -> None:
    """Сводка по модулю — ЧЕСТНАЯ, cash-aware:

    Раньше показывали Foyda через JournalEntry (accrual) — продал на 25М,
    в hub писали «+25М foyda» хотя клиент дал 0. Теперь:
      - Sotildi (otgruzilgan): из SaleOrder.amount_uzs
      - To'landi (kassa):     SaleOrder.paid_amount_uzs
      - Qarz (mijoz qarz):    разница

      - Xarid qilindi:        PurchaseOrder.amount_uzs
      - To'landi:             PurchaseOrder.paid_amount_uzs
      - Qarz biz:             разница

    Нигде нет «Foyda» — она требует учёта себестоимости и не может быть
    cash-honest без отдельной оценки. Лучше показать факт, чем красивую
    но врущую цифру.
    """
    from apps.modules.models import Module

    org = ctx.org()
    try:
        module = Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        send_message(ctx.chat_id, "Modul topilmadi.")
        return

    lines = [f"{_label(module_code)}", f"<i>{module.name}</i>", ""]

    # 1. Cash-honest финансы (30 дней)
    cash = _module_cash_view(org, module_code, days=30)
    if cash["sales_invoiced"] > 0 or cash["purchases_invoiced"] > 0:
        lines.append("<b>💰 Moliya (30 kun):</b>")
        if cash["sales_invoiced"] > 0:
            lines.append(
                f"  📤 Sotildi:    <code>{_fmt_money(cash['sales_invoiced'])}</code> so'm"
            )
            lines.append(
                f"     ↳ to'landi: <code>{_fmt_money(cash['sales_paid'])}</code> · "
                f"qarz: <b>{_fmt_money(cash['sales_debt'])}</b>"
            )
        if cash["purchases_invoiced"] > 0:
            lines.append(
                f"  📥 Xaridlar:   <code>{_fmt_money(cash['purchases_invoiced'])}</code> so'm"
            )
            lines.append(
                f"     ↳ to'landi: <code>{_fmt_money(cash['purchases_paid'])}</code> · "
                f"qarz biz: <b>{_fmt_money(cash['purchases_debt'])}</b>"
            )
        lines.append("")
    else:
        lines.append("<i>Oxirgi 30 kunda sotuv/xarid yo'q.</i>")
        lines.append("")

    # 2. Склады модуля
    wh_summary = _module_warehouses_summary(org, module)
    if wh_summary['count'] > 0:
        lines.append(f"<b>📦 Omborlar ({wh_summary['count']}):</b>")
        for wh in wh_summary['list'][:5]:
            lines.append(f"  • {wh['code']} · {wh['name']}")
        if wh_summary['count'] > 5:
            lines.append(f"  … va yana {wh_summary['count'] - 5} ta")
        lines.append("")

    # 3. Партии
    lots = _module_lots_summary(org, module_code)
    if lots:
        lines.append(f"<b>📋 Partiyalar:</b>")
        for label, value in lots.items():
            lines.append(f"  {label}: <b>{value}</b>")
        lines.append("")

    markup = kb([("← Modullar", "home:modules"), ("🏠 Bosh", "home")], cols=2)
    _send_or_edit(ctx, "\n".join(lines), markup)


def _module_cash_view(org, module_code: str, *, days: int) -> dict:
    """Cash-honest cum-aggregat по модулю за period.

    Sales: distinct SaleOrder где есть item с source-FK этого модуля.
    Purchases: PurchaseOrder.module прямо.
    Возвращаем: invoiced/paid/debt для каждой стороны.
    """
    from datetime import date, timedelta
    from django.db.models import Q, Sum
    from apps.purchases.models import PurchaseOrder
    from apps.sales.models import SaleOrder

    today = date.today()
    df = today - timedelta(days=days)

    # Продажи модуля: фильтр по source-FK item'ов.
    so_qs = SaleOrder.objects.filter(
        organization=org, status=SaleOrder.Status.CONFIRMED,
        date__gte=df, date__lte=today,
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
        # stock — нет специфичной привязки sale-item, отдаём пусто
        so_qs = so_qs.none()

    so_agg = so_qs.distinct().aggregate(
        invoiced=Sum("amount_uzs"),
        paid=Sum("paid_amount_uzs"),
    )
    sales_invoiced = Decimal(so_agg["invoiced"] or 0)
    sales_paid = Decimal(so_agg["paid"] or 0)

    # Закупки модуля — прямой module FK на PurchaseOrder.
    po_agg = (
        PurchaseOrder.objects
        .filter(
            organization=org, module__code=module_code,
            status=PurchaseOrder.Status.CONFIRMED,
            date__gte=df, date__lte=today,
        )
        .aggregate(
            invoiced=Sum("amount_uzs"),
            paid=Sum("paid_amount_uzs"),
        )
    )
    purchases_invoiced = Decimal(po_agg["invoiced"] or 0)
    purchases_paid = Decimal(po_agg["paid"] or 0)

    return {
        "sales_invoiced": sales_invoiced,
        "sales_paid": sales_paid,
        "sales_debt": sales_invoiced - sales_paid,
        "purchases_invoiced": purchases_invoiced,
        "purchases_paid": purchases_paid,
        "purchases_debt": purchases_invoiced - purchases_paid,
    }


def _module_warehouses_summary(org, module) -> dict:
    """Список складов модуля (только активные)."""
    from apps.warehouses.models import Warehouse

    qs = (
        Warehouse.objects
        .filter(organization=org, module=module, is_active=True)
        .order_by("code")
    )
    items = list(qs)
    return {
        "count": len(items),
        "list": [{"code": w.code, "name": w.name} for w in items],
    }


def _module_lots_summary(org, module_code: str) -> dict | None:
    """Куда: для feed/feedlot/slaughter/matochnik — кол-во активных партий."""
    summary: dict = {}

    if module_code == "feed":
        from apps.feed.models import FeedBagLot, FeedBatch
        approved = FeedBatch.objects.filter(
            organization=org, status=FeedBatch.Status.APPROVED,
        ).count()
        bags = FeedBagLot.objects.filter(
            organization=org, status=FeedBagLot.Status.ACTIVE,
        ).count()
        if approved or bags:
            summary["Tasdiqlangan partiya"] = approved
            summary["Faol qoplar"] = bags
    elif module_code == "feedlot":
        from apps.feedlot.models import FeedlotBatch
        active = FeedlotBatch.objects.filter(
            organization=org,
            status__in=[
                FeedlotBatch.Status.PLACED,
                FeedlotBatch.Status.GROWING,
                FeedlotBatch.Status.READY_SLAUGHTER,
            ],
        ).count()
        if active:
            summary["Faol partiya"] = active
    elif module_code == "vet":
        from apps.vet.models import VetStockBatch
        avail = VetStockBatch.objects.filter(
            organization=org, status=VetStockBatch.Status.AVAILABLE,
        ).count()
        if avail:
            summary["Mavjud lot"] = avail
    elif module_code == "matochnik":
        from apps.matochnik.models import BreedingHerd
        active = BreedingHerd.objects.filter(
            organization=org,
        ).exclude(status="depopulated").count()
        if active:
            summary["Faol poda"] = active
    elif module_code == "incubation":
        from apps.incubation.models import IncubationRun
        active = IncubationRun.objects.filter(
            organization=org,
        ).exclude(status__in=["hatched", "cancelled"]).count()
        if active:
            summary["Faol partiya"] = active
    elif module_code == "slaughter":
        from apps.slaughter.models import SlaughterRun
        recent = SlaughterRun.objects.filter(organization=org).count()
        if recent:
            summary["Jami partiya"] = recent

    return summary or None


# ─── Hisobotlar — также по модулям ────────────────────────────────────────


def render_reports_modules(ctx: HandlerCtx) -> None:
    """Список модулей в разрезе аналитики. Каждый → детальный report."""
    from apps.common.permissions import level_satisfies
    from apps.modules.models import OrganizationModule

    org = ctx.org()
    levels = user_module_levels(ctx.link)
    owner = is_owner(levels)

    enabled_codes = set(
        OrganizationModule.objects
        .filter(organization=org, is_enabled=True)
        .values_list("module__code", flat=True)
    )
    # Для отчётов добавляем sales/purchases (они отдельно от production).
    report_codes = PRODUCTION_MODULE_CODES + ["sales", "purchases"]
    visible = [
        c for c in report_codes
        if c in enabled_codes
        and (owner or level_satisfies(levels.get(c, "none"), "r"))
    ]

    if not visible:
        _send_or_edit(
            ctx,
            "📊 <b>Hisobotlar</b>\n\nFaol modul yo'q.",
            kb([("← Orqaga", "home")], cols=1),
        )
        return

    text = (
        "📊 <b>Hisobotlar</b>\n\n"
        "Modul tanlang — uning to'liq analitikasi (oxirgi 30 kun)."
    )
    buttons = [(_label(c), f"rep:{c}") for c in visible]
    buttons.append(("← Orqaga", "home"))
    _send_or_edit(ctx, text, kb(buttons, cols=2))


@on_callback("rep")
def handle_report_module_callback(ctx: HandlerCtx) -> None:
    if not ctx.args:
        return
    code = ctx.args[0]

    from apps.common.permissions import level_satisfies
    levels = user_module_levels(ctx.link)
    if not (is_owner(levels) or level_satisfies(levels.get(code, "none"), "r")):
        send_message(ctx.chat_id, f"⛔ Modulga ruxsat yo'q: {_label(code)}")
        return

    _render_module_report(ctx, module_code=code)


def _render_module_report(ctx: HandlerCtx, *, module_code: str) -> None:
    """Детальная аналитика модуля — cash-honest, без обманчивого «Foyda».

    Раньше выводили Daromad/Xarajat/Foyda через JournalEntry — это
    accrual (по факту накладной), а не cash. У клиента долг 24M, в
    Foyda стояло «+25M» — пользователь возмущался.

    Теперь чисто:
      - Sotuv (otgruzilgan / to'langan / qarz)
      - Xarid (olingan / to'langan / qarz biz)
      - Per-module: кол-во партий

    Сравнение 7 vs 30 дней показывает динамику.
    """
    from apps.modules.models import Module

    org = ctx.org()
    try:
        Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        send_message(ctx.chat_id, "Modul topilmadi.")
        return

    week = _module_cash_view(org, module_code, days=7)
    month = _module_cash_view(org, module_code, days=30)

    lines = [
        f"📊 {_label(module_code)} · <b>analitika</b>",
        "",
    ]

    # Sales-блок (если есть данные)
    if month["sales_invoiced"] > 0 or week["sales_invoiced"] > 0:
        lines.append("<b>📤 Sotuvlar (7 / 30 kun):</b>")
        lines.append(
            f"  Otgruzilgan: "
            f"<code>{_fmt_money(week['sales_invoiced'])}</code> / "
            f"<code>{_fmt_money(month['sales_invoiced'])}</code>"
        )
        lines.append(
            f"  To'langan:   "
            f"<code>{_fmt_money(week['sales_paid'])}</code> / "
            f"<code>{_fmt_money(month['sales_paid'])}</code>"
        )
        lines.append(
            f"  Qarz:        "
            f"<code>{_fmt_money(week['sales_debt'])}</code> / "
            f"<b>{_fmt_money(month['sales_debt'])}</b>"
        )
        # Honesty hint: процент оплат
        if month["sales_invoiced"] > 0:
            pct = (month["sales_paid"] / month["sales_invoiced"]) * 100
            lines.append(f"  ─ to'lov darajasi (30 kun): <b>{pct:.0f}%</b>")
        lines.append("")

    # Purchases-блок
    if month["purchases_invoiced"] > 0 or week["purchases_invoiced"] > 0:
        lines.append("<b>📥 Xaridlar (7 / 30 kun):</b>")
        lines.append(
            f"  Olingan:     "
            f"<code>{_fmt_money(week['purchases_invoiced'])}</code> / "
            f"<code>{_fmt_money(month['purchases_invoiced'])}</code>"
        )
        lines.append(
            f"  To'langan:   "
            f"<code>{_fmt_money(week['purchases_paid'])}</code> / "
            f"<code>{_fmt_money(month['purchases_paid'])}</code>"
        )
        lines.append(
            f"  Qarz biz:    "
            f"<code>{_fmt_money(week['purchases_debt'])}</code> / "
            f"<b>{_fmt_money(month['purchases_debt'])}</b>"
        )
        lines.append("")

    if (
        month["sales_invoiced"] == 0
        and month["purchases_invoiced"] == 0
        and week["sales_invoiced"] == 0
    ):
        lines.append("<i>Oxirgi 30 kunda harakatlar yo'q.</i>")
        lines.append("")

    # Партии (production-модули)
    lots = _module_lots_summary(org, module_code)
    if lots:
        lines.append("<b>📋 Partiyalar:</b>")
        for label, value in lots.items():
            lines.append(f"  {label}: <b>{value}</b>")

    markup = kb([("← Hisobotlar", "home:reports"), ("🏠 Bosh", "home")], cols=2)
    _send_or_edit(ctx, "\n".join(lines), markup)
