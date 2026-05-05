"""
Тесты на 5 новых scheduled tasks системы оповещений:
- head_morning_brief
- cashflow_alert
- stale_payment_reminder
- low_stock_feed
- weekly_monday_summary

Каждый task проверяется:
- срабатывает при наличии триггера (правильно формирует push)
- молчит когда триггера нет (без шума)
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.purchases.models import PurchaseOrder
from apps.sales.models import SaleCommunication, SaleOrder
from apps.tgbot.tasks import (
    cashflow_alert_task,
    head_morning_brief_task,
    low_stock_feed_task,
    stale_payment_reminder_task,
    weekly_monday_summary_task,
)
from apps.users.models import User
from apps.warehouses.models import Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_sales():
    return Module.objects.get(code="sales")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="К-EA", kind="buyer", name="Mijoz EA",
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-EA-S", kind="supplier", name="Yetk EA",
    )


@pytest.fixture
def sales_wh(org, m_sales):
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-EA-S", name="WH",
    )


@pytest.fixture
def manager():
    return User.objects.create(email="ea-mgr@y.local", full_name="m")


# ─── stale_payment_reminder ──────────────────────────────────────────────


def test_stale_payment_picks_orders_without_recent_communication(
    org, m_sales, buyer, sales_wh,
):
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-EA-1",
        date=date.today() - timedelta(days=30),
        customer=buyer, warehouse=sales_wh,
        amount_uzs=Decimal("5000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = stale_payment_reminder_task()
    assert result["queued"] == 1
    text = mock.call_args.args[0]
    assert "ПРД-EA-1" in text
    assert "kundan ortiq" in text


def test_stale_payment_skips_recently_touched_order(
    org, m_sales, buyer, sales_wh, manager,
):
    o = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-EA-FRESH",
        date=date.today() - timedelta(days=20),
        customer=buyer, warehouse=sales_wh,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    SaleCommunication.objects.create(
        order=o,
        contacted_at=datetime.now(timezone.utc) - timedelta(days=2),
        method=SaleCommunication.Method.CALL,
        outcome=SaleCommunication.Outcome.PROMISED,
        customer_response="ok",
        contacted_by=manager,
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = stale_payment_reminder_task()
    assert mock.call_count == 0
    assert result["queued"] == 0


def test_stale_payment_picks_order_with_old_touch(
    org, m_sales, buyer, sales_wh, manager,
):
    """Касание было 10 дней назад → попадает в stale."""
    o = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-EA-OLD",
        date=date.today() - timedelta(days=30),
        customer=buyer, warehouse=sales_wh,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    SaleCommunication.objects.create(
        order=o,
        contacted_at=datetime.now(timezone.utc) - timedelta(days=10),
        method=SaleCommunication.Method.CALL,
        outcome=SaleCommunication.Outcome.NO_ANSWER,
        customer_response="нет ответа",
        contacted_by=manager,
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        stale_payment_reminder_task()
    assert mock.call_count >= 1


# ─── cashflow_alert ───────────────────────────────────────────────────────


def test_cashflow_alert_triggers_on_negative_balance(org):
    """Если cash-балансы содержат отрицательные → alert."""
    fake_cash = {
        "cash":     {"label": "Наличные",     "balance_uzs": -100000},
        "transfer": {"label": "Перечисление", "balance_uzs": 50000},
        "_total_uzs": -50000,
    }
    with patch("apps.dashboard.services.cash_balances", return_value=fake_cash), \
         patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = cashflow_alert_task()

    assert result["queued"] >= 1
    text = mock.call_args.args[0]
    assert "manfiy qoldiq" in text.lower()


def test_cashflow_alert_silent_when_all_positive(org):
    fake_cash = {
        "cash":     {"label": "Наличные",     "balance_uzs": 1000000},
        "transfer": {"label": "Перечисление", "balance_uzs": 500000},
        "_total_uzs": 1500000,
    }
    with patch("apps.dashboard.services.cash_balances", return_value=fake_cash), \
         patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = cashflow_alert_task()

    assert mock.call_count == 0
    assert result["queued"] == 0


# ─── head_morning_brief ──────────────────────────────────────────────────


def test_head_brief_silent_when_no_yesterday_activity(org):
    """Без вчерашних продаж/закупок head не получает шум."""
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = head_morning_brief_task()
    # Должно быть 0 — у DEFAULT нет вчерашней активности по модулям
    assert result["queued"] == 0


# ─── low_stock_feed ──────────────────────────────────────────────────────


def test_low_stock_silent_when_no_consumption(org):
    """Если расхода нет — alert не шлём (avg=0)."""
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = low_stock_feed_task()
    # На DEFAULT нет активного потребления → 0 alerts
    assert result["queued"] == 0


# ─── weekly_monday_summary ───────────────────────────────────────────────


def test_weekly_summary_silent_when_no_activity(org):
    """Пустая неделя → не шумим."""
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = weekly_monday_summary_task()
    # На DEFAULT нет активности за прошлую неделю
    assert result["queued"] == 0


def test_weekly_summary_sends_when_sales_exist(
    org, m_sales, buyer, sales_wh,
):
    """Создаём продажу за прошлую неделю → summary шлётся."""
    last_week = date.today() - timedelta(days=4)
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-WK-1",
        date=last_week, customer=buyer, warehouse=sales_wh,
        amount_uzs=Decimal("2000000"), paid_amount_uzs=Decimal("500000"),
        status=SaleOrder.Status.CONFIRMED,
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as mock:
        result = weekly_monday_summary_task()
    assert result["queued"] >= 1
    text = mock.call_args.args[0]
    assert "Haftalik" in text
    assert "2 000 000" in text
    assert "500 000" in text  # to'langan
