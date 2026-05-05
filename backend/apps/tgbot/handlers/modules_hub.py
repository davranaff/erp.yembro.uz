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

MODULE_LABELS_UZ = {
    "matochnik":  "🐔 Onalik",
    "incubation": "🥚 Inkubatsiya",
    "feedlot":    "🍗 Bo'rdoqi",
    "slaughter":  "🔪 So'yish",
    "feed":       "🌾 Yem-xashak",
    "vet":        "💊 Vet-aptek",
    "stock":      "📦 Ombor",
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
    """Сводка по модулю: финансы (касса/прибыль) + склады + партии."""
    from apps.modules.models import Module

    org = ctx.org()
    try:
        module = Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        send_message(ctx.chat_id, "Modul topilmadi.")
        return

    lines = [f"{_label(module_code)}", f"<i>{module.name}</i>", ""]

    # 1. Финансы по модулю — sum(JE) за последние 30 дней
    fin = _module_finance_30d(org, module)
    lines.append("<b>💰 Moliya (oxirgi 30 kun):</b>")
    lines.append(f"  Daromad:  <code>{_fmt_money(fin['revenue'])}</code> so'm")
    lines.append(f"  Xarajat:  <code>{_fmt_money(fin['expense'])}</code> so'm")
    profit = fin['revenue'] - fin['expense']
    sign = "+" if profit >= 0 else "−"
    lines.append(
        f"  Foyda:    <b>{sign}{_fmt_money(abs(profit))}</b> so'm"
    )
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

    # 3. Партии (если применимо)
    lots = _module_lots_summary(org, module_code)
    if lots:
        lines.append(f"<b>📋 Partiyalar:</b>")
        for label, value in lots.items():
            lines.append(f"  {label}: <b>{value}</b>")
        lines.append("")

    markup = kb([("← Modullar", "home:modules"), ("🏠 Bosh", "home")], cols=2)
    _send_or_edit(ctx, "\n".join(lines), markup)


def _module_finance_30d(org, module) -> dict:
    """Доход/расход модуля за последние 30 дней через JournalEntry.module FK."""
    from datetime import date, timedelta
    from django.db.models import Sum
    from apps.accounting.models import GLAccount, JournalEntry

    today = date.today()
    df = today - timedelta(days=30)

    # Доходы (account.type=income, kredit JE по нашему модулю)
    revenue = (
        JournalEntry.objects
        .filter(
            organization=org, module=module,
            entry_date__gte=df, entry_date__lte=today,
            credit_subaccount__account__type=GLAccount.Type.INCOME,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    expense = (
        JournalEntry.objects
        .filter(
            organization=org, module=module,
            entry_date__gte=df, entry_date__lte=today,
            debit_subaccount__account__type=GLAccount.Type.EXPENSE,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    return {"revenue": revenue, "expense": expense}


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
    """Детальная аналитика модуля: финансы за неделю/месяц, обороты, KPI."""
    from datetime import date, timedelta
    from django.db.models import Sum
    from apps.modules.models import Module

    org = ctx.org()
    try:
        module = Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        send_message(ctx.chat_id, "Modul topilmadi.")
        return

    today = date.today()
    df_week = today - timedelta(days=7)
    df_month = today - timedelta(days=30)

    fin_week = _module_finance_range(org, module, df_week, today)
    fin_month = _module_finance_range(org, module, df_month, today)

    lines = [
        f"📊 {_label(module_code)} · <b>analitika</b>",
        "",
        "<b>7 kun:</b>",
        f"  Daromad:  <code>{_fmt_money(fin_week['revenue'])}</code>",
        f"  Xarajat:  <code>{_fmt_money(fin_week['expense'])}</code>",
        f"  Foyda:    <b>{_fmt_signed(fin_week['revenue'] - fin_week['expense'])}</b>",
        "",
        "<b>30 kun:</b>",
        f"  Daromad:  <code>{_fmt_money(fin_month['revenue'])}</code>",
        f"  Xarajat:  <code>{_fmt_money(fin_month['expense'])}</code>",
        f"  Foyda:    <b>{_fmt_signed(fin_month['revenue'] - fin_month['expense'])}</b>",
    ]

    # Module-specific KPI
    if module_code == "sales":
        from apps.sales.models import SaleOrder
        agg = (
            SaleOrder.objects
            .filter(
                organization=org, status=SaleOrder.Status.CONFIRMED,
                date__gte=df_month, date__lte=today,
            )
            .aggregate(
                total=Sum("amount_uzs"),
                paid=Sum("paid_amount_uzs"),
            )
        )
        total = Decimal(agg["total"] or 0)
        paid = Decimal(agg["paid"] or 0)
        debt = total - paid
        lines.append("")
        lines.append("<b>Sotuvlar (30 kun):</b>")
        lines.append(f"  Otgruzilgan: <code>{_fmt_money(total)}</code>")
        lines.append(f"  To'langan:   <code>{_fmt_money(paid)}</code>")
        lines.append(f"  Qarz:        <code>{_fmt_money(debt)}</code>")
    elif module_code == "purchases":
        from apps.purchases.models import PurchaseOrder
        agg = (
            PurchaseOrder.objects
            .filter(
                organization=org, status=PurchaseOrder.Status.CONFIRMED,
                date__gte=df_month, date__lte=today,
            )
            .aggregate(
                total=Sum("amount_uzs"),
                paid=Sum("paid_amount_uzs"),
            )
        )
        total = Decimal(agg["total"] or 0)
        paid = Decimal(agg["paid"] or 0)
        debt = total - paid
        lines.append("")
        lines.append("<b>Xaridlar (30 kun):</b>")
        lines.append(f"  Olingan:     <code>{_fmt_money(total)}</code>")
        lines.append(f"  To'langan:   <code>{_fmt_money(paid)}</code>")
        lines.append(f"  Qarz biz:    <code>{_fmt_money(debt)}</code>")
    else:
        # Production-модули: показать кол-во партий
        lots = _module_lots_summary(org, module_code)
        if lots:
            lines.append("")
            lines.append("<b>Partiyalar:</b>")
            for label, value in lots.items():
                lines.append(f"  {label}: <b>{value}</b>")

    markup = kb([("← Hisobotlar", "home:reports"), ("🏠 Bosh", "home")], cols=2)
    _send_or_edit(ctx, "\n".join(lines), markup)


def _module_finance_range(org, module, df, dt) -> dict:
    from django.db.models import Sum
    from apps.accounting.models import GLAccount, JournalEntry

    revenue = (
        JournalEntry.objects
        .filter(
            organization=org, module=module,
            entry_date__gte=df, entry_date__lte=dt,
            credit_subaccount__account__type=GLAccount.Type.INCOME,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    expense = (
        JournalEntry.objects
        .filter(
            organization=org, module=module,
            entry_date__gte=df, entry_date__lte=dt,
            debit_subaccount__account__type=GLAccount.Type.EXPENSE,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    return {"revenue": revenue, "expense": expense}


def _fmt_signed(v) -> str:
    n = Decimal(str(v))
    if n == 0:
        return "0"
    return f"{'+' if n > 0 else '−'}{_fmt_money(abs(n))}"
