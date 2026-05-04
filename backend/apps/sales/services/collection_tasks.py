"""
Workflow задач по сбору дебиторки.

Это «lite»-таска без отдельной таблицы Task — мы вычисляем задачи
на лету из существующих сигналов:

  1. CALLBACK_DUE   — у касания `next_action_date <= today`, оплата не пришла
  2. PROMISE_BROKEN — клиент обещал (`promised_pay_date <= today`),
                      но счёт всё ещё не оплачен
  3. FORECAST_DUE   — менеджер прогнозировал (`expected_pay_date <= today`),
                      но оплата не пришла
  4. ESCALATION     — счёт просрочен > 60 дней И последнее касание было
                      больше 7 дней назад (или касаний вообще не было)

Источник данных — `SaleCommunication` + `SaleOrder` + `compute_aging_report`.

Каждая задача снабжена `priority`:
    high   — escalation
    medium — promise_broken / forecast_due
    low    — callback_due (плановый обзвон)

Для FE-странички /tasks возвращаем словарь с массивами по типам и счётчиками.
Для cron-таска — то же самое, но можно фильтровать по сотруднику.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls, timedelta
from decimal import Decimal
from typing import Optional

from django.db.models import OuterRef, Subquery, Max, Q

from apps.sales.models import SaleCommunication, SaleOrder


ESCALATION_OVERDUE_THRESHOLD_DAYS = 60
ESCALATION_NO_TOUCH_THRESHOLD_DAYS = 7


@dataclass
class CollectionTask:
    type: str          # callback_due | promise_broken | forecast_due | escalation
    priority: str      # high | medium | low
    order_id: str
    order_doc: str
    customer_id: str
    customer_name: str
    customer_code: str
    outstanding_uzs: Decimal
    days_overdue: int
    title: str
    detail: str
    # Опциональные поля, в зависимости от типа
    communication_id: Optional[str] = None
    promised_date: Optional[date_cls] = None
    expected_date: Optional[date_cls] = None
    callback_date: Optional[date_cls] = None
    last_touch_date: Optional[date_cls] = None
    contacted_by_name: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "priority": self.priority,
            "order_id": self.order_id,
            "order_doc": self.order_doc,
            "customer_id": self.customer_id,
            "customer_name": self.customer_name,
            "customer_code": self.customer_code,
            "outstanding_uzs": str(self.outstanding_uzs),
            "days_overdue": self.days_overdue,
            "title": self.title,
            "detail": self.detail,
            "communication_id": self.communication_id,
            "promised_date": (
                self.promised_date.isoformat() if self.promised_date else None
            ),
            "expected_date": (
                self.expected_date.isoformat() if self.expected_date else None
            ),
            "callback_date": (
                self.callback_date.isoformat() if self.callback_date else None
            ),
            "last_touch_date": (
                self.last_touch_date.isoformat() if self.last_touch_date else None
            ),
            "contacted_by_name": self.contacted_by_name,
        }


@dataclass
class CollectionTasksReport:
    callback_due: list[CollectionTask] = field(default_factory=list)
    promise_broken: list[CollectionTask] = field(default_factory=list)
    forecast_due: list[CollectionTask] = field(default_factory=list)
    escalation: list[CollectionTask] = field(default_factory=list)
    as_of: date_cls = field(default_factory=date_cls.today)

    @property
    def total(self) -> int:
        return (
            len(self.callback_due) + len(self.promise_broken)
            + len(self.forecast_due) + len(self.escalation)
        )

    def to_dict(self) -> dict:
        return {
            "as_of": self.as_of.isoformat(),
            "total": self.total,
            "counts": {
                "callback_due": len(self.callback_due),
                "promise_broken": len(self.promise_broken),
                "forecast_due": len(self.forecast_due),
                "escalation": len(self.escalation),
            },
            "callback_due": [t.to_dict() for t in self.callback_due],
            "promise_broken": [t.to_dict() for t in self.promise_broken],
            "forecast_due": [t.to_dict() for t in self.forecast_due],
            "escalation": [t.to_dict() for t in self.escalation],
        }


def _outstanding(order: SaleOrder) -> Decimal:
    return Decimal(order.amount_uzs or 0) - Decimal(order.paid_amount_uzs or 0)


def _basis_date(order: SaleOrder) -> date_cls:
    return order.due_date or order.date


def compute_collection_tasks(
    organization,
    *,
    today: Optional[date_cls] = None,
    contacted_by=None,
) -> CollectionTasksReport:
    """Вычислить задачи по сбору дебиторки на сегодня.

    `contacted_by` — опционально сужает callback_due/promise_broken/forecast_due
    до касаний конкретного сотрудника. Эскалации остаются глобальными.
    """
    today = today or date_cls.today()
    report = CollectionTasksReport(as_of=today)

    unpaid_orders = (
        SaleOrder.objects
        .filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .select_related("customer")
    )

    # Indexed lookup для O(1) доступа к заказу при обходе касаний
    orders_by_id = {o.id: o for o in unpaid_orders}
    if not orders_by_id:
        return report

    # ── Pulled из SaleCommunication ─────────────────────────────────────
    # Для каждого order_id берём последнее касание с непустым
    # next_action_date / promised_pay_date / expected_pay_date.
    comms_qs = (
        SaleCommunication.objects
        .filter(
            order_id__in=orders_by_id.keys(),
            order__organization=organization,
        )
        .select_related("contacted_by", "order__customer")
    )
    if contacted_by is not None:
        comms_qs = comms_qs.filter(contacted_by=contacted_by)

    # Группируем самое свежее касание на каждый order для каждого сигнала
    latest_callback: dict = {}
    latest_promise: dict = {}
    latest_expected: dict = {}
    for c in comms_qs.order_by("-contacted_at"):
        oid = c.order_id
        if c.next_action_date and oid not in latest_callback:
            latest_callback[oid] = c
        if c.promised_pay_date and oid not in latest_promise:
            latest_promise[oid] = c
        if c.expected_pay_date and oid not in latest_expected:
            latest_expected[oid] = c

    # ── 1. CALLBACK_DUE ─────────────────────────────────────────────────
    for oid, c in latest_callback.items():
        if c.next_action_date is None or c.next_action_date > today:
            continue
        order = orders_by_id[oid]
        out = _outstanding(order)
        if out <= 0:
            continue
        days_late = (today - c.next_action_date).days
        report.callback_due.append(CollectionTask(
            type="callback_due",
            priority="low" if days_late == 0 else "medium",
            order_id=str(order.id),
            order_doc=order.doc_number,
            customer_id=str(order.customer_id),
            customer_name=order.customer.name,
            customer_code=order.customer.code,
            outstanding_uzs=out,
            days_overdue=(today - _basis_date(order)).days,
            title="Запланированный обзвон",
            detail=(
                f"Перезвонить — назначено на {c.next_action_date}"
                + (f" (просрочка {days_late} дн)" if days_late > 0 else " (сегодня)")
            ),
            communication_id=str(c.id),
            callback_date=c.next_action_date,
            contacted_by_name=(
                getattr(c.contacted_by, "full_name", None)
                or getattr(c.contacted_by, "email", None)
                if c.contacted_by_id else None
            ),
        ))

    # ── 2. PROMISE_BROKEN ───────────────────────────────────────────────
    for oid, c in latest_promise.items():
        if c.promised_pay_date is None or c.promised_pay_date >= today:
            continue
        order = orders_by_id[oid]
        out = _outstanding(order)
        if out <= 0:
            continue
        days_late = (today - c.promised_pay_date).days
        report.promise_broken.append(CollectionTask(
            type="promise_broken",
            priority="high" if days_late > 7 else "medium",
            order_id=str(order.id),
            order_doc=order.doc_number,
            customer_id=str(order.customer_id),
            customer_name=order.customer.name,
            customer_code=order.customer.code,
            outstanding_uzs=out,
            days_overdue=(today - _basis_date(order)).days,
            title="Клиент не сдержал обещание",
            detail=(
                f"Обещал заплатить {c.promised_pay_date}, "
                f"прошло {days_late} дн без оплаты."
            ),
            communication_id=str(c.id),
            promised_date=c.promised_pay_date,
            contacted_by_name=(
                getattr(c.contacted_by, "full_name", None)
                or getattr(c.contacted_by, "email", None)
                if c.contacted_by_id else None
            ),
        ))

    # ── 3. FORECAST_DUE ─────────────────────────────────────────────────
    for oid, c in latest_expected.items():
        if c.expected_pay_date is None or c.expected_pay_date >= today:
            continue
        order = orders_by_id[oid]
        out = _outstanding(order)
        if out <= 0:
            continue
        days_late = (today - c.expected_pay_date).days
        report.forecast_due.append(CollectionTask(
            type="forecast_due",
            priority="medium",
            order_id=str(order.id),
            order_doc=order.doc_number,
            customer_id=str(order.customer_id),
            customer_name=order.customer.name,
            customer_code=order.customer.code,
            outstanding_uzs=out,
            days_overdue=(today - _basis_date(order)).days,
            title="Не пришла прогнозная оплата",
            detail=(
                f"Прогнозировали оплату к {c.expected_pay_date}, "
                f"прошло {days_late} дн."
            ),
            communication_id=str(c.id),
            expected_date=c.expected_pay_date,
            contacted_by_name=(
                getattr(c.contacted_by, "full_name", None)
                or getattr(c.contacted_by, "email", None)
                if c.contacted_by_id else None
            ),
        ))

    # ── 4. ESCALATION (глобально, не зависит от contacted_by) ───────────
    # Долг 60+ дней без касания за последние 7 дней.
    last_touch_subq = (
        SaleCommunication.objects
        .filter(order=OuterRef("pk"), order__organization=organization)
        .order_by("-contacted_at")
        .values("contacted_at")[:1]
    )
    overdue_orders = (
        SaleOrder.objects
        .filter(
            organization=organization,
            status=SaleOrder.Status.CONFIRMED,
        )
        .exclude(payment_status=SaleOrder.PaymentStatus.PAID)
        .annotate(last_touch=Subquery(last_touch_subq))
        .select_related("customer")
    )
    cutoff_no_touch = today - timedelta(days=ESCALATION_NO_TOUCH_THRESHOLD_DAYS)
    for order in overdue_orders:
        out = _outstanding(order)
        if out <= 0:
            continue
        days_overdue = (today - _basis_date(order)).days
        if days_overdue < ESCALATION_OVERDUE_THRESHOLD_DAYS:
            continue
        last_touch_date = order.last_touch.date() if order.last_touch else None
        if last_touch_date and last_touch_date >= cutoff_no_touch:
            # Был свежий контакт — пока не эскалируем
            continue
        report.escalation.append(CollectionTask(
            type="escalation",
            priority="high",
            order_id=str(order.id),
            order_doc=order.doc_number,
            customer_id=str(order.customer_id),
            customer_name=order.customer.name,
            customer_code=order.customer.code,
            outstanding_uzs=out,
            days_overdue=days_overdue,
            title="Эскалация — нужна реакция руководителя",
            detail=(
                f"Долг {days_overdue} дн, "
                + (
                    f"последнее касание {last_touch_date} "
                    f"({(today - last_touch_date).days} дн назад)."
                    if last_touch_date else "касаний по этому счёту вообще не было."
                )
            ),
            last_touch_date=last_touch_date,
        ))

    # Сортируем каждую категорию по убыванию суммы — чтобы наверху были
    # самые «дорогие» проблемы.
    for bucket in (
        report.callback_due, report.promise_broken,
        report.forecast_due, report.escalation,
    ):
        bucket.sort(key=lambda t: t.outstanding_uzs, reverse=True)

    return report
