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

from django.db.models import Count, Q, Sum

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


def kpi_summary(organization, *, today: Optional[date] = None) -> dict:
    """Базовые KPI: денежные потоки + остатки за период."""
    start, end = _month_bounds(today)

    # `purchases_confirmed_uzs` = полный объём закупок периода (начисление),
    # `purchases_paid_uzs` = реально оплаченная поставщикам часть. Симметрично
    # продажам; непогашенный долг по закупкам виден отдельно как
    # `creditor_balance_uzs`.
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

    # ── Продажи за период ───────────────────────────────────────────────
    # `sales_revenue_uzs` = реально оплаченная клиентами часть (актуальные
    # деньги), долг в эту цифру НЕ попадает — он виден отдельно как
    # `sales_unpaid_uzs` и в общей дебиторке. `sales_invoiced_uzs` —
    # полный объём отгрузок (начисление), вторичная метрика.
    # `sales_margin_uzs` — валовая маржа по отгрузке (accrual): выручка
    # сопоставляется со своей себестоимостью независимо от факта оплаты.
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
    sales_margin = sales_invoiced - sales_cost

    # ── Дебиторка (что должны нам) — по всем не-paid SaleOrder ──────────
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

    # ── Черновики, ждущие действия ──────────────────────────────────────
    purchases_drafts = PurchaseOrder.objects.filter(
        organization=organization, status=PurchaseOrder.Status.DRAFT,
    ).count()
    sales_drafts = SaleOrder.objects.filter(
        organization=organization, status=SaleOrder.Status.DRAFT,
    ).count()
    payments_drafts = Payment.objects.filter(
        organization=organization,
        status__in=[Payment.Status.DRAFT, Payment.Status.CONFIRMED],
    ).count()

    active_batches = Batch.objects.filter(
        organization=organization, state=Batch.State.ACTIVE
    ).count()

    transfers_pending = InterModuleTransfer.objects.filter(
        organization=organization,
        state__in=[
            InterModuleTransfer.State.AWAITING_ACCEPTANCE,
            InterModuleTransfer.State.UNDER_REVIEW,
        ],
    ).count()

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
        "active_batches": active_batches,
        "transfers_pending": transfers_pending,
        "purchases_drafts": purchases_drafts,
        "sales_drafts": sales_drafts,
        "payments_drafts": payments_drafts,
    }


def production_summary(organization) -> dict:
    """Сколько голов/партий в каждом производственном модуле сейчас."""
    breeding_heads = (
        BreedingHerd.objects.filter(
            organization=organization,
            status__in=[
                BreedingHerd.Status.GROWING,
                BreedingHerd.Status.PRODUCING,
            ],
        ).aggregate(s=Sum("current_heads"))["s"]
        or 0
    )
    feedlot_heads = (
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
    incubation_runs = IncubationRun.objects.filter(
        organization=organization,
        status__in=[
            IncubationRun.Status.INCUBATING,
            IncubationRun.Status.HATCHING,
        ],
    ).count()
    incubation_eggs = (
        IncubationRun.objects.filter(
            organization=organization,
            status__in=[
                IncubationRun.Status.INCUBATING,
                IncubationRun.Status.HATCHING,
            ],
        ).aggregate(s=Sum("eggs_loaded"))["s"]
        or 0
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
