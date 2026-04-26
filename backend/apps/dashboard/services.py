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

    purchases_total = (
        PurchaseOrder.objects.filter(
            organization=organization,
            status=PurchaseOrder.Status.CONFIRMED,
            date__gte=start, date__lte=end,
        ).aggregate(s=Sum("amount_uzs"))["s"]
        or Decimal("0")
    )

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
    sales_agg = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
            date__gte=start, date__lte=end,
        ).aggregate(
            revenue=Sum("amount_uzs"),
            cost=Sum("cost_uzs"),
        )
    )
    sales_revenue = sales_agg["revenue"] or Decimal("0")
    sales_cost = sales_agg["cost"] or Decimal("0")
    sales_margin = sales_revenue - sales_cost

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
        "creditor_balance_uzs": str(creditor),
        "debtor_balance_uzs": str(debtor),
        "payments_in_uzs": str(pay_in_month),
        "payments_out_uzs": str(pay_out_month),
        "sales_revenue_uzs": str(sales_revenue),
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
