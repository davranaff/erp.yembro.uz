"""
Сервисы холдинговой консолидации.

Текущий MVP: агрегаты по тем Organization, где у user есть активный
membership. Без новой модели Holding — холдинг = множество организаций,
доступных пользователю.

Метрики на компанию:
    - выручка по приходам (incoming payments) за период
    - расходы по уходящим платежам за период
    - сумма закупок confirmed за период
    - дебиторка = sum(amount_uzs - paid_amount_uzs) по SaleOrder не-PAID
    - кредиторка = sum(amount_uzs - paid_amount_uzs) по PO в not-PAID
    - активные batches (state=ACTIVE)
    - активные модули
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable, Optional

from django.db.models import Q, Sum, Count

from apps.batches.models import Batch
from apps.modules.models import OrganizationModule
from apps.organizations.models import Organization
from apps.payments.models import Payment
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleOrder


@dataclass
class CompanyConsolidation:
    id: str
    code: str
    name: str
    direction: str
    accounting_currency: str
    is_active: bool

    purchases_confirmed_uzs: str
    payments_in_uzs: str
    payments_out_uzs: str
    creditor_balance_uzs: str  # сколько мы должны поставщикам
    debtor_balance_uzs: str   # сколько нам должны покупатели
    active_batches: int
    modules_count: int

    period_from: str
    period_to: str

    def to_dict(self) -> dict:
        return asdict(self)


def _default_period() -> tuple[date, date]:
    """Период по умолчанию — текущий месяц."""
    today = date.today()
    start = today.replace(day=1)
    return start, today


def consolidate(
    organizations: Iterable[Organization],
    *,
    period_from: Optional[date] = None,
    period_to: Optional[date] = None,
) -> list[CompanyConsolidation]:
    if period_from is None or period_to is None:
        d_from, d_to = _default_period()
        period_from = period_from or d_from
        period_to = period_to or d_to

    out: list[CompanyConsolidation] = []
    for org in organizations:
        purchases_total = (
            PurchaseOrder.objects.filter(
                organization=org,
                status=PurchaseOrder.Status.CONFIRMED,
                date__gte=period_from,
                date__lte=period_to,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )

        creditor = (
            PurchaseOrder.objects.filter(
                organization=org,
                status=PurchaseOrder.Status.CONFIRMED,
            )
            .exclude(payment_status=PurchaseOrder.PaymentStatus.PAID)
            .aggregate(
                amt=Sum("amount_uzs"),
                paid=Sum("paid_amount_uzs"),
            )
        )
        creditor_balance = (creditor["amt"] or Decimal("0")) - (
            creditor["paid"] or Decimal("0")
        )
        if creditor_balance < 0:
            creditor_balance = Decimal("0")

        debtor = (
            SaleOrder.objects.filter(
                organization=org,
                status=SaleOrder.Status.CONFIRMED,
            )
            .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
            .aggregate(
                amt=Sum("amount_uzs"),
                paid=Sum("paid_amount_uzs"),
            )
        )
        debtor_balance = (debtor["amt"] or Decimal("0")) - (
            debtor["paid"] or Decimal("0")
        )
        if debtor_balance < 0:
            debtor_balance = Decimal("0")

        pay_in = (
            Payment.objects.filter(
                organization=org,
                status=Payment.Status.POSTED,
                direction=Payment.Direction.IN,
                date__gte=period_from,
                date__lte=period_to,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )
        pay_out = (
            Payment.objects.filter(
                organization=org,
                status=Payment.Status.POSTED,
                direction=Payment.Direction.OUT,
                date__gte=period_from,
                date__lte=period_to,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )

        active_batches = Batch.objects.filter(
            organization=org, state=Batch.State.ACTIVE
        ).count()

        modules_count = OrganizationModule.objects.filter(
            organization=org, is_enabled=True
        ).count()

        out.append(
            CompanyConsolidation(
                id=str(org.id),
                code=org.code,
                name=org.name,
                direction=org.direction,
                accounting_currency=(
                    org.accounting_currency.code
                    if org.accounting_currency_id
                    else ""
                ),
                is_active=org.is_active,
                purchases_confirmed_uzs=str(purchases_total),
                payments_in_uzs=str(pay_in),
                payments_out_uzs=str(pay_out),
                creditor_balance_uzs=str(creditor_balance),
                debtor_balance_uzs=str(debtor_balance),
                active_batches=active_batches,
                modules_count=modules_count,
                period_from=period_from.isoformat(),
                period_to=period_to.isoformat(),
            )
        )
    return out


def total_kpis(rows: list[CompanyConsolidation]) -> dict:
    """Сводные KPI по холдингу."""
    if not rows:
        return {
            "companies": 0,
            "modules": 0,
            "active_batches": 0,
            "purchases_confirmed_uzs": "0",
            "payments_in_uzs": "0",
            "payments_out_uzs": "0",
            "creditor_balance_uzs": "0",
        "debtor_balance_uzs": "0",
        }
    return {
        "companies": len(rows),
        "modules": sum(r.modules_count for r in rows),
        "active_batches": sum(r.active_batches for r in rows),
        "purchases_confirmed_uzs": str(
            sum((Decimal(r.purchases_confirmed_uzs) for r in rows), Decimal("0"))
        ),
        "payments_in_uzs": str(
            sum((Decimal(r.payments_in_uzs) for r in rows), Decimal("0"))
        ),
        "payments_out_uzs": str(
            sum((Decimal(r.payments_out_uzs) for r in rows), Decimal("0"))
        ),
        "creditor_balance_uzs": str(
            sum((Decimal(r.creditor_balance_uzs) for r in rows), Decimal("0"))
        ),
        "debtor_balance_uzs": str(
            sum((Decimal(r.debtor_balance_uzs) for r in rows), Decimal("0"))
        ),
    }
