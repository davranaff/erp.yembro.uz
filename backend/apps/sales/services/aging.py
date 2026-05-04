"""
AR Aging report — отчёт о старении дебиторской задолженности.

Группирует непогашенные SaleOrder по бакетам:
    current   : ещё не наступил срок (today < basis_date)
    0-30      : 1-30 дней просрочки
    31-60     : 31-60 дней просрочки
    61-90     : 61-90 дней просрочки
    90+       : более 90 дней

`basis_date` = `due_date` если задан, иначе fallback на `date` продажи.
Это стандартная индустриальная практика: без явного срока считаем что
оплата ожидалась в день продажи (immediate payment terms).

Источник истины — `payment_status` + `paid_amount_uzs` на SaleOrder.
Отдельной AR-таблицы не нужно: при confirm/payment эти поля уже обновлены.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date as date_cls
from decimal import Decimal
from typing import Optional

from apps.sales.models import SaleOrder


# Границы бакетов в днях просрочки (включительно сверху).
# Менять с осторожностью — FE-формат завязан на эти ключи.
BUCKET_THRESHOLDS = (30, 60, 90)
BUCKET_KEYS = ("current", "b_0_30", "b_31_60", "b_61_90", "b_90_plus")


def _bucket_for_days_overdue(days_overdue: int) -> str:
    """Маппит количество дней просрочки в ключ бакета.

    days_overdue < 0  → 'current' (ещё не просрочено)
    1..30             → 'b_0_30'
    31..60            → 'b_31_60'
    61..90            → 'b_61_90'
    91+               → 'b_90_plus'
    """
    if days_overdue <= 0:
        return "current"
    if days_overdue <= BUCKET_THRESHOLDS[0]:
        return "b_0_30"
    if days_overdue <= BUCKET_THRESHOLDS[1]:
        return "b_31_60"
    if days_overdue <= BUCKET_THRESHOLDS[2]:
        return "b_61_90"
    return "b_90_plus"


@dataclass
class AgingRow:
    counterparty_id: str
    code: str
    name: str
    current: Decimal = Decimal("0")
    b_0_30: Decimal = Decimal("0")
    b_31_60: Decimal = Decimal("0")
    b_61_90: Decimal = Decimal("0")
    b_90_plus: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    oldest_overdue_days: int = 0
    orders_count: int = 0
    # Для удобства FE-сортировки и алертов: есть ли просрочка вообще
    has_overdue: bool = False

    def to_dict(self) -> dict:
        return {
            "counterparty_id": self.counterparty_id,
            "code": self.code,
            "name": self.name,
            "current": str(self.current),
            "b_0_30": str(self.b_0_30),
            "b_31_60": str(self.b_31_60),
            "b_61_90": str(self.b_61_90),
            "b_90_plus": str(self.b_90_plus),
            "total": str(self.total),
            "oldest_overdue_days": self.oldest_overdue_days,
            "orders_count": self.orders_count,
            "has_overdue": self.has_overdue,
        }


@dataclass
class AgingReport:
    rows: list[AgingRow] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    as_of: date_cls = field(default_factory=date_cls.today)

    def to_dict(self) -> dict:
        return {
            "rows": [r.to_dict() for r in self.rows],
            "summary": self.summary,
            "as_of": self.as_of.isoformat(),
        }


def compute_aging_report(
    organization,
    *,
    today: Optional[date_cls] = None,
    customer_id: Optional[str] = None,
) -> AgingReport:
    """Считает aging-отчёт по дебиторке организации.

    Параметры:
        organization: org для которой считаем
        today:        опциональная override для тестов
        customer_id:  если задан — фильтр на одного клиента
                      (используется в карточке должника)

    Возвращает AgingReport с rows (по контрагенту) и summary (агрегаты).
    Контрагенты с нулевым total в результат не попадают.
    """
    today = today or date_cls.today()

    qs = (
        SaleOrder.objects.filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .select_related("customer")
        .only(
            "id",
            "amount_uzs",
            "paid_amount_uzs",
            "date",
            "due_date",
            "customer_id",
            "customer__code",
            "customer__name",
        )
    )
    if customer_id:
        qs = qs.filter(customer_id=customer_id)

    rows_by_customer: dict[str, AgingRow] = {}

    for order in qs:
        if order.customer_id is None:
            continue
        outstanding = (order.amount_uzs or Decimal("0")) - (
            order.paid_amount_uzs or Decimal("0")
        )
        if outstanding <= 0:
            continue

        # Базовая дата для расчёта просрочки: due_date если задан,
        # иначе сама дата продажи (immediate payment terms по умолчанию).
        basis_date = order.due_date or order.date
        days_overdue = (today - basis_date).days
        bucket = _bucket_for_days_overdue(days_overdue)

        cp_id = str(order.customer_id)
        row = rows_by_customer.get(cp_id)
        if row is None:
            row = AgingRow(
                counterparty_id=cp_id,
                code=order.customer.code,
                name=order.customer.name,
            )
            rows_by_customer[cp_id] = row

        # Прибавляем outstanding в нужный бакет
        setattr(row, bucket, getattr(row, bucket) + outstanding)
        row.total += outstanding
        row.orders_count += 1
        if days_overdue > 0:
            row.has_overdue = True
            if days_overdue > row.oldest_overdue_days:
                row.oldest_overdue_days = days_overdue

    rows = list(rows_by_customer.values())
    # Топ должников сверху (по total убыванию)
    rows.sort(key=lambda r: r.total, reverse=True)

    # Summary: суммы по бакетам + counts
    summary_totals = defaultdict(lambda: Decimal("0"))
    for r in rows:
        summary_totals["current"] += r.current
        summary_totals["b_0_30"] += r.b_0_30
        summary_totals["b_31_60"] += r.b_31_60
        summary_totals["b_61_90"] += r.b_61_90
        summary_totals["b_90_plus"] += r.b_90_plus
        summary_totals["total"] += r.total

    summary = {
        "current": str(summary_totals["current"]),
        "b_0_30": str(summary_totals["b_0_30"]),
        "b_31_60": str(summary_totals["b_31_60"]),
        "b_61_90": str(summary_totals["b_61_90"]),
        "b_90_plus": str(summary_totals["b_90_plus"]),
        "total": str(summary_totals["total"]),
        "customers_count": len(rows),
        "overdue_customers_count": sum(1 for r in rows if r.has_overdue),
    }

    return AgingReport(rows=rows, summary=summary, as_of=today)
