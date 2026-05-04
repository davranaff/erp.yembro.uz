"""
Тесты `compute_collection_tasks` — workflow задач по сбору дебиторки.

Покрывают:
  - callback_due: касание с next_action_date <= today
  - promise_broken: касание с promised_pay_date < today, не оплачено
  - forecast_due: касание с expected_pay_date < today, не оплачено
  - escalation: долг 60+ дней + касание не было > 7 дней
  - PAID-заказы НЕ дают задач
  - mine-фильтр работает на callback/promise/forecast, escalation глобальна
  - sort by outstanding desc
"""
from datetime import date, datetime, time, timedelta, timezone as dt_tz
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.sales.models import SaleCommunication, SaleOrder
from apps.sales.services.collection_tasks import (
    ESCALATION_OVERDUE_THRESHOLD_DAYS,
    compute_collection_tasks,
)
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="K-T-1", kind="buyer", name="ООО Тест",
    )


@pytest.fixture
def buyer2(org):
    return Counterparty.objects.create(
        organization=org, code="K-T-2", kind="buyer", name="ИП Юг",
    )


@pytest.fixture
def warehouse(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter, code="СК-T", name="Скл T",
    )


@pytest.fixture
def alice():
    return User.objects.create(email="alice-tasks@y.local", full_name="Alice")


@pytest.fixture
def bob():
    return User.objects.create(email="bob-tasks@y.local", full_name="Bob")


def _mk_order(
    org, m, buyer, warehouse, *, doc, amount, sale_date, due_date, paid=Decimal("0"),
):
    return SaleOrder.objects.create(
        organization=org, doc_number=doc,
        date=sale_date, due_date=due_date,
        module=m, customer=buyer, warehouse=warehouse,
        status=SaleOrder.Status.CONFIRMED,
        payment_status=(
            SaleOrder.PaymentStatus.PARTIAL if 0 < paid < amount
            else SaleOrder.PaymentStatus.UNPAID if paid == 0
            else SaleOrder.PaymentStatus.PAID
        ),
        amount_uzs=amount, paid_amount_uzs=paid,
    )


def _mk_comm(order, by, *, when=None, callback=None, promise=None, expected=None,
             outcome="other"):
    return SaleCommunication.objects.create(
        order=order,
        contacted_at=when or timezone.now(),
        method="call", outcome=outcome,
        customer_response="тест",
        promised_pay_date=promise,
        expected_pay_date=expected,
        next_action_date=callback,
        contacted_by=by,
    )


# ─── callback_due ────────────────────────────────────────────────────────


def test_callback_due_includes_today_callback(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-CB-1", amount=Decimal("100000"),
                      sale_date=date(2026, 5, 25), due_date=date(2026, 5, 25))
    _mk_comm(order, alice, callback=today)
    report = compute_collection_tasks(org, today=today)
    assert len(report.callback_due) == 1
    assert report.callback_due[0].order_doc == "П-T-CB-1"
    assert report.callback_due[0].priority == "low"


def test_callback_due_skips_future_callback(org, m_slaughter, buyer, warehouse, alice):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-CB-2", amount=Decimal("1"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(order, alice, callback=date(2026, 6, 5))
    report = compute_collection_tasks(org, today=today)
    assert report.callback_due == []


def test_callback_due_priority_medium_when_overdue(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-CB-3", amount=Decimal("1"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(order, alice, callback=date(2026, 5, 28))  # 4 дня просрочен callback
    report = compute_collection_tasks(org, today=today)
    assert len(report.callback_due) == 1
    assert report.callback_due[0].priority == "medium"


# ─── promise_broken ──────────────────────────────────────────────────────


def test_promise_broken_when_promised_date_passed(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-PR-1", amount=Decimal("500000"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 15))
    _mk_comm(order, alice, promise=date(2026, 5, 25))
    report = compute_collection_tasks(org, today=today)
    assert len(report.promise_broken) == 1
    assert report.promise_broken[0].promised_date == date(2026, 5, 25)


def test_promise_broken_high_priority_when_late_more_than_7d(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-PR-2", amount=Decimal("1"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(order, alice, promise=date(2026, 5, 20))  # 12 дней просрочки
    report = compute_collection_tasks(org, today=today)
    assert report.promise_broken[0].priority == "high"


# ─── forecast_due ────────────────────────────────────────────────────────


def test_forecast_due_when_expected_passed(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-FC-1", amount=Decimal("250000"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(order, alice, expected=date(2026, 5, 28))
    report = compute_collection_tasks(org, today=today)
    assert len(report.forecast_due) == 1
    assert report.forecast_due[0].expected_date == date(2026, 5, 28)


# ─── escalation ──────────────────────────────────────────────────────────


def test_escalation_when_overdue_60d_no_recent_touch(
    org, m_slaughter, buyer, warehouse,
):
    today = date(2026, 6, 1)
    sale_date = today - timedelta(days=70)  # 70 дней просрочки
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-ESC-1", amount=Decimal("999"),
                      sale_date=sale_date, due_date=sale_date)
    report = compute_collection_tasks(org, today=today)
    assert len(report.escalation) == 1
    assert report.escalation[0].priority == "high"
    assert report.escalation[0].days_overdue == 70


def test_escalation_skipped_when_recent_touch(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    sale_date = today - timedelta(days=70)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-ESC-2", amount=Decimal("1"),
                      sale_date=sale_date, due_date=sale_date)
    # Был контакт за день до отчётной даты → эскалация снимается.
    # Используем datetime относительно теста, не relative-real-now.
    recent = datetime.combine(today - timedelta(days=1), time(12, 0), tzinfo=dt_tz.utc)
    _mk_comm(order, alice, when=recent)
    report = compute_collection_tasks(org, today=today)
    assert report.escalation == []


def test_escalation_skipped_when_overdue_under_threshold(
    org, m_slaughter, buyer, warehouse,
):
    today = date(2026, 6, 1)
    sale_date = today - timedelta(days=ESCALATION_OVERDUE_THRESHOLD_DAYS - 5)
    _mk_order(org, m_slaughter, buyer, warehouse,
              doc="П-T-ESC-3", amount=Decimal("1"),
              sale_date=sale_date, due_date=sale_date)
    report = compute_collection_tasks(org, today=today)
    assert report.escalation == []


# ─── exclusions / filters ────────────────────────────────────────────────


def test_paid_orders_dont_produce_tasks(
    org, m_slaughter, buyer, warehouse, alice,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-PAID", amount=Decimal("100"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1),
                      paid=Decimal("100"))
    _mk_comm(order, alice, callback=today, promise=date(2026, 5, 20),
             expected=date(2026, 5, 20))
    report = compute_collection_tasks(org, today=today)
    assert report.total == 0


def test_mine_filter_excludes_other_users_callback(
    org, m_slaughter, buyer, warehouse, alice, bob,
):
    today = date(2026, 6, 1)
    order = _mk_order(org, m_slaughter, buyer, warehouse,
                      doc="П-T-MN-1", amount=Decimal("1"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(order, alice, callback=today)
    # alice видит свой callback
    report_alice = compute_collection_tasks(org, today=today, contacted_by=alice)
    assert len(report_alice.callback_due) == 1
    # bob — нет
    report_bob = compute_collection_tasks(org, today=today, contacted_by=bob)
    assert report_bob.callback_due == []


def test_sort_by_outstanding_desc(
    org, m_slaughter, buyer, buyer2, warehouse, alice,
):
    today = date(2026, 6, 1)
    big = _mk_order(org, m_slaughter, buyer, warehouse,
                    doc="П-T-BIG", amount=Decimal("10000000"),
                    sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    small = _mk_order(org, m_slaughter, buyer2, warehouse,
                      doc="П-T-SML", amount=Decimal("100"),
                      sale_date=date(2026, 5, 1), due_date=date(2026, 5, 1))
    _mk_comm(big, alice, promise=date(2026, 5, 20))
    _mk_comm(small, alice, promise=date(2026, 5, 20))
    report = compute_collection_tasks(org, today=today)
    docs = [t.order_doc for t in report.promise_broken]
    assert docs == ["П-T-BIG", "П-T-SML"]
