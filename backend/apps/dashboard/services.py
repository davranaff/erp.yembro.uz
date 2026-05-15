"""
Сервисы агрегатов для главной страницы (Dashboard).

Все агрегаты — в контексте текущей organization (request.organization).
Никакой кросс-org работы — для холдинга есть apps/holding.
"""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum

from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch
from apps.incubation.models import IncubationRun
from apps.matochnik.models import BreedingHerd
from apps.payments.models import Payment
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleOrder
from apps.transfers.models import InterModuleTransfer


def _month_bounds(today: Optional[date] = None) -> tuple[date, date]:
    today = today or date.today()
    start = today.replace(day=1)
    return start, today


def kpi_summary(organization, *, readable_modules: Optional[set] = None, today: Optional[date] = None) -> dict:
    """Базовые KPI: денежные потоки + остатки за период.

    readable_modules — set of module codes the user can read (≥r). None means
    unlimited (superuser). Controls which non-financial counters are included.
    Financial aggregates are always computed org-wide; the view strips them via
    _strip_financial_kpis when the user lacks ledger.r.
    """
    start, end = _month_bounds(today)

    def _can_see(module_code: str) -> bool:
        return readable_modules is None or module_code in readable_modules

    # ── Financial aggregates (org-wide; view strips if not finances_visible) ──
    purchases_agg = PurchaseOrder.objects.filter(
        organization=organization,
        status=PurchaseOrder.Status.CONFIRMED,
        date__gte=start, date__lte=end,
    ).aggregate(invoiced=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    purchases_total = purchases_agg["invoiced"] or Decimal("0")
    purchases_paid = purchases_agg["paid"] or Decimal("0")

    creditor_agg = (
        PurchaseOrder.objects.filter(
            organization=organization,
            status=PurchaseOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
        .aggregate(amt=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    )
    creditor = (creditor_agg["amt"] or Decimal("0")) - (
        creditor_agg["paid"] or Decimal("0")
    )
    if creditor < 0:
        creditor = Decimal("0")

    pay_in_month = (
        Payment.objects.filter(
            organization=organization,
            status=Payment.Status.POSTED,
            direction=Payment.Direction.IN,
            date__gte=start, date__lte=end,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )
    pay_out_month = (
        Payment.objects.filter(
            organization=organization,
            status=Payment.Status.POSTED,
            direction=Payment.Direction.OUT,
            date__gte=start, date__lte=end,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )

    today_date = today or date.today()

    sales_agg = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=start, date__lte=end,
        ).aggregate(
            invoiced=Sum("amount_uzs"),
            paid=Sum("paid_amount_uzs"),
            cost=Sum("cost_uzs"),
        )
    )
    sales_invoiced = sales_agg["invoiced"] or Decimal("0")
    sales_paid = sales_agg["paid"] or Decimal("0")
    sales_cost = sales_agg["cost"] or Decimal("0")
    sales_unpaid = sales_invoiced - sales_paid

    # Cash-basis margin: for each order, only count the paid portion of cost.
    # paid_cost_i = cost_i * (paid_i / amount_i)  →  margin contribution = paid_i - paid_cost_i
    # Filter amount_uzs > 0 to avoid division by zero.
    paid_margin_agg = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=start, date__lte=end,
            amount_uzs__gt=0,
        ).annotate(
            paid_cost_portion=ExpressionWrapper(
                F("cost_uzs") * F("paid_amount_uzs") / F("amount_uzs"),
                output_field=DecimalField(max_digits=20, decimal_places=2),
            )
        ).aggregate(
            total_paid=Sum("paid_amount_uzs"),
            total_paid_cost=Sum("paid_cost_portion"),
        )
    )
    sales_margin = (paid_margin_agg["total_paid"] or Decimal("0")) - (
        paid_margin_agg["total_paid_cost"] or Decimal("0")
    )

    # Forecast: unpaid on this month's orders where due_date is in the future
    # (or null — not yet explicitly overdue).
    _month_unpaid_qs = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=start, date__lte=end,
        ).exclude(payment_status=SaleOrder.PaymentStatus.PAID)
    )
    forecast_agg = _month_unpaid_qs.filter(
        Q(due_date__gte=today_date) | Q(due_date__isnull=True)
    ).aggregate(amt=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    sales_forecast = max(
        (forecast_agg["amt"] or Decimal("0")) - (forecast_agg["paid"] or Decimal("0")),
        Decimal("0"),
    )

    # Overdue loss: unpaid amounts on this month's orders past their due_date.
    loss_agg = _month_unpaid_qs.filter(
        due_date__lt=today_date
    ).aggregate(amt=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    sales_overdue_loss = max(
        (loss_agg["amt"] or Decimal("0")) - (loss_agg["paid"] or Decimal("0")),
        Decimal("0"),
    )

    debtor_agg = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .aggregate(amt=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    )
    debtor = (debtor_agg["amt"] or Decimal("0")) - (
        debtor_agg["paid"] or Decimal("0")
    )
    if debtor < 0:
        debtor = Decimal("0")

    # ── Module-scoped counts (None when user lacks access to that module) ──
    purchases_drafts = (
        PurchaseOrder.objects.filter(
            organization=organization, status=PurchaseOrder.Status.DRAFT,
        ).count()
        if _can_see("purchases") else None
    )
    sales_drafts = (
        SaleOrder.objects.filter(
            organization=organization, status=SaleOrder.Status.DRAFT,
        ).count()
        if _can_see("sales") else None
    )
    payments_drafts = (
        Payment.objects.filter(
            organization=organization,
            status__in=[Payment.Status.DRAFT, Payment.Status.CONFIRMED],
        ).count()
        if _can_see("ledger") else None
    )

    # active_batches: only batches in modules the user can read
    batches_qs = Batch.objects.filter(
        organization=organization, state=Batch.State.ACTIVE,
    )
    if readable_modules is not None:
        batches_qs = batches_qs.filter(current_module__code__in=readable_modules)
    active_batches = batches_qs.count()

    # transfers_pending: transfers where the user's module is source or dest
    transfers_qs = InterModuleTransfer.objects.filter(
        organization=organization,
        state__in=[
            InterModuleTransfer.State.AWAITING_ACCEPTANCE,
            InterModuleTransfer.State.UNDER_REVIEW,
        ],
    )
    if readable_modules is not None:
        transfers_qs = transfers_qs.filter(
            Q(from_module__code__in=readable_modules) | Q(to_module__code__in=readable_modules)
        )
    transfers_pending = transfers_qs.count()

    return {
        "period": {"from": start.isoformat(), "to": end.isoformat()},
        "purchases_confirmed_uzs": str(purchases_total),
        "purchases_paid_uzs": str(purchases_paid),
        "creditor_balance_uzs": str(creditor),
        "debtor_balance_uzs": str(debtor),
        "payments_in_uzs": str(pay_in_month),
        "payments_out_uzs": str(pay_out_month),
        "sales_revenue_uzs": str(sales_paid),
        "sales_invoiced_uzs": str(sales_invoiced),
        "sales_unpaid_uzs": str(sales_unpaid),
        "sales_cost_uzs": str(sales_cost),
        "sales_margin_uzs": str(sales_margin),
        "sales_forecast_uzs": str(sales_forecast),
        "sales_overdue_loss_uzs": str(sales_overdue_loss),
        "active_batches": active_batches,
        "transfers_pending": transfers_pending,
        "purchases_drafts": purchases_drafts,
        "sales_drafts": sales_drafts,
        "payments_drafts": payments_drafts,
    }


def production_summary(organization, *, readable_modules: Optional[set] = None) -> dict:
    """Сколько голов/партий в каждом производственном модуле сейчас.

    readable_modules — set of module codes the user can read. None = unlimited.
    Modules not in readable_modules return None; the frontend hides those tiles.
    """
    def _can_see(module_code: str) -> bool:
        return readable_modules is None or module_code in readable_modules

    breeding_heads = (
        (
            BreedingHerd.objects.filter(
                organization=organization,
                status__in=[
                    BreedingHerd.Status.GROWING,
                    BreedingHerd.Status.PRODUCING,
                ],
            ).aggregate(s=Sum("current_heads"))["s"]
            or 0
        )
        if _can_see("matochnik") else None
    )
    feedlot_heads = (
        (
            FeedlotBatch.objects.filter(
                organization=organization,
                status__in=[
                    FeedlotBatch.Status.PLACED,
                    FeedlotBatch.Status.GROWING,
                    FeedlotBatch.Status.READY_SLAUGHTER,
                ],
            ).aggregate(s=Sum("current_heads"))["s"]
            or 0
        )
        if _can_see("feedlot") else None
    )
    incubation_runs = (
        IncubationRun.objects.filter(
            organization=organization,
            status__in=[
                IncubationRun.Status.INCUBATING,
                IncubationRun.Status.HATCHING,
            ],
        ).count()
        if _can_see("incubation") else None
    )
    incubation_eggs = (
        (
            IncubationRun.objects.filter(
                organization=organization,
                status__in=[
                    IncubationRun.Status.INCUBATING,
                    IncubationRun.Status.HATCHING,
                ],
            ).aggregate(s=Sum("eggs_loaded"))["s"]
            or 0
        )
        if _can_see("incubation") else None
    )

    return {
        "matochnik_heads": breeding_heads,
        "feedlot_heads": feedlot_heads,
        "incubation_runs": incubation_runs,
        "incubation_eggs_loaded": incubation_eggs,
    }


def cash_balances(organization) -> dict:
    """
    Остатки кассы по каналам (приход − расход среди POSTED платежей).
    Для real-баланса нужен GL turnover; это упрощённая фронт-метрика.

    Возвращает словарь по каналам + ключ `_total_uzs` со сводным остатком
    (касса + банк + click + прочее).
    """
    out: dict = {}
    total = Decimal("0")
    for ch_value, ch_label in Payment.Channel.choices:
        in_sum = (
            Payment.objects.filter(
                organization=organization,
                status=Payment.Status.POSTED,
                channel=ch_value,
                direction=Payment.Direction.IN,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )
        out_sum = (
            Payment.objects.filter(
                organization=organization,
                status=Payment.Status.POSTED,
                channel=ch_value,
                direction=Payment.Direction.OUT,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )
        balance = in_sum - out_sum
        total += balance
        out[ch_value] = {
            "label": ch_label,
            "balance_uzs": str(balance),
        }
    out["_total_uzs"] = str(total)
    return out


def ar_summary(organization, *, days_for_dso: int = 90) -> dict:
    """AR (дебиторка) — снимок для главной страницы и /reports.

    Возвращает:
      - aging buckets (current/0-30/31-60/61-90/90+) — totals
      - dso (Days Sales Outstanding) — за последние `days_for_dso` дней
      - top-3 должников по total
      - overdue_customers_count
      - total_ar
      - total_overdue (всё кроме current)

    DSO = (current_AR / revenue_за_период) * days
    Если выручки в периоде нет → DSO = None.
    """
    from apps.sales.services.aging import compute_aging_report
    from apps.sales.models import SaleOrder

    report = compute_aging_report(organization)
    summary = report.summary
    rows = report.rows

    total_overdue = (
        Decimal(summary["b_0_30"])
        + Decimal(summary["b_31_60"])
        + Decimal(summary["b_61_90"])
        + Decimal(summary["b_90_plus"])
    )

    # DSO: AR / средняя дневная выручка за `days_for_dso` дней.
    today = date.today()
    period_start = today - timedelta(days=days_for_dso)
    revenue_in_period = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=period_start, date__lte=today,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )
    if revenue_in_period > 0:
        dso = (Decimal(summary["total"]) / revenue_in_period) * Decimal(
            days_for_dso
        )
        dso_value = float(dso.quantize(Decimal("0.1")))
    else:
        dso_value = None

    top_debtors = [
        {
            "counterparty_id": r.counterparty_id,
            "code": r.code,
            "name": r.name,
            "total": str(r.total),
            "oldest_overdue_days": r.oldest_overdue_days,
        }
        for r in rows[:3]
    ]

    return {
        "as_of": today.isoformat(),
        "buckets": {
            "current": summary["current"],
            "b_0_30": summary["b_0_30"],
            "b_31_60": summary["b_31_60"],
            "b_61_90": summary["b_61_90"],
            "b_90_plus": summary["b_90_plus"],
        },
        "total_ar_uzs": summary["total"],
        "total_overdue_uzs": str(total_overdue),
        "customers_count": summary["customers_count"],
        "overdue_customers_count": summary["overdue_customers_count"],
        "dso_days": dso_value,
        "dso_window_days": days_for_dso,
        "revenue_in_window_uzs": str(revenue_in_period),
        "top_debtors": top_debtors,
    }


def cashflow_chart(organization, *, days: int = 30) -> list[dict]:
    """
    Кэш-флоу за N дней: на каждую дату — суммы in/out POSTED платежей.
    """
    today = date.today()
    start = today - timedelta(days=days - 1)

    in_qs = (
        Payment.objects.filter(
            organization=organization,
            status=Payment.Status.POSTED,
            direction=Payment.Direction.IN,
            date__gte=start, date__lte=today,
        )
        .values("date")
        .annotate(s=Sum("amount_uzs"))
    )
    out_qs = (
        Payment.objects.filter(
            organization=organization,
            status=Payment.Status.POSTED,
            direction=Payment.Direction.OUT,
            date__gte=start, date__lte=today,
        )
        .values("date")
        .annotate(s=Sum("amount_uzs"))
    )

    in_map = {row["date"]: row["s"] for row in in_qs}
    out_map = {row["date"]: row["s"] for row in out_qs}

    points: list[dict] = []
    cur = start
    while cur <= today:
        points.append({
            "date": cur.isoformat(),
            "in_uzs": str(in_map.get(cur, Decimal("0"))),
            "out_uzs": str(out_map.get(cur, Decimal("0"))),
        })
        cur += timedelta(days=1)
    return points


def module_cash_balances(
    organization,
    *,
    readable_modules: Optional[set] = None,
    today: Optional[date] = None,
) -> list[dict]:
    """Per-module cash balances for the dashboard kassas section.

    Returns one entry per module that has any POSTED payment activity.
    Filtered by readable_modules — modules the user cannot read are excluded.
    Each entry includes all-time balance and current-period in/out.
    """
    from apps.modules.models import Module

    start, end = _month_bounds(today)

    base = Payment.objects.filter(
        organization=organization,
        status=Payment.Status.POSTED,
        module__isnull=False,
    )

    module_ids = list(base.values_list("module_id", flat=True).distinct())
    if not module_ids:
        return []

    modules = Module.objects.filter(id__in=module_ids).order_by("name")
    result = []

    for module in modules:
        if readable_modules is not None and module.code not in readable_modules:
            continue

        mqs = base.filter(module=module)

        balance_in = mqs.filter(direction=Payment.Direction.IN).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        balance_out = mqs.filter(direction=Payment.Direction.OUT).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        balance = balance_in - balance_out

        period_in = mqs.filter(direction=Payment.Direction.IN, date__gte=start, date__lte=end).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
        period_out = mqs.filter(direction=Payment.Direction.OUT, date__gte=start, date__lte=end).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")

        result.append({
            "module_code": module.code,
            "module_name": module.name,
            "balance_uzs": str(balance),
            "period_in_uzs": str(period_in),
            "period_out_uzs": str(period_out),
        })

    return sorted(result, key=lambda x: Decimal(x["balance_uzs"]), reverse=True)


def module_kpi(
    organization,
    module_code: str,
    *,
    date_from: date,
    date_to: date,
) -> dict:
    """Per-module KPIs for the module section on the dashboard.

    Aggregates POSTED payments and CONFIRMED SaleOrders scoped to a single
    module. Used by DashboardModuleView — the view enforces RBAC before calling.
    """
    base = Payment.objects.filter(
        organization=organization,
        status=Payment.Status.POSTED,
        module__code=module_code,
    )

    period_in = (
        base.filter(direction=Payment.Direction.IN, date__gte=date_from, date__lte=date_to)
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    period_out = (
        base.filter(direction=Payment.Direction.OUT, date__gte=date_from, date__lte=date_to)
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )

    all_in = base.filter(direction=Payment.Direction.IN).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    all_out = base.filter(direction=Payment.Direction.OUT).aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    balance = all_in - all_out

    ar_agg = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            module__code=module_code,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .aggregate(amt=Sum("amount_uzs"), paid=Sum("paid_amount_uzs"))
    )
    ar = max(
        (ar_agg["amt"] or Decimal("0")) - (ar_agg["paid"] or Decimal("0")),
        Decimal("0"),
    )

    sales_drafts = SaleOrder.objects.filter(
        organization=organization,
        status=SaleOrder.Status.DRAFT,
        module__code=module_code,
    ).count()

    purchases_drafts = PurchaseOrder.objects.filter(
        organization=organization,
        status=PurchaseOrder.Status.DRAFT,
        module__code=module_code,
    ).count()

    in_by_date = {
        r["date"]: r["s"]
        for r in base.filter(
            direction=Payment.Direction.IN,
            date__gte=date_from, date__lte=date_to,
        ).values("date").annotate(s=Sum("amount_uzs"))
    }
    out_by_date = {
        r["date"]: r["s"]
        for r in base.filter(
            direction=Payment.Direction.OUT,
            date__gte=date_from, date__lte=date_to,
        ).values("date").annotate(s=Sum("amount_uzs"))
    }

    cashflow: list[dict] = []
    cur = date_from
    while cur <= date_to:
        cashflow.append({
            "date": cur.isoformat(),
            "in_uzs": str(in_by_date.get(cur, Decimal("0"))),
            "out_uzs": str(out_by_date.get(cur, Decimal("0"))),
        })
        cur += timedelta(days=1)

    return {
        "module_code": module_code,
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "payments_in_uzs": str(period_in),
        "payments_out_uzs": str(period_out),
        "balance_uzs": str(balance),
        "ar_uzs": str(ar),
        "sales_drafts": sales_drafts,
        "purchases_drafts": purchases_drafts,
        "cashflow": cashflow,
    }
