"""
Тесты client-focused scheduled tasks: promise_broken / pre_block_warning
+ escalation tones в debt-reminder.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.sales.models import SaleCommunication, SaleOrder
from apps.tgbot.notifications import (
    fmt_debt_reminder_uz,
    fmt_pre_block_warning_uz,
    fmt_promise_broken_uz,
)
from apps.tgbot.tasks import (
    pre_block_warning_daily_task,
    promise_broken_daily_task,
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
        organization=org, code="К-CFT", kind="buyer", name="Mijoz CFT",
        credit_limit_uzs=Decimal("10000000"),
    )


@pytest.fixture
def warehouse(org, m_sales):
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-CFT", name="WH",
    )


@pytest.fixture
def manager():
    return User.objects.create(email="cft-mgr@y.local", full_name="Mgr")


# ─── promise_broken ──────────────────────────────────────────────────────


def test_promise_broken_picks_yesterday_promised(
    org, m_sales, buyer, warehouse, manager,
):
    """Communication.promised_pay_date == yesterday + order не оплачен → push."""
    yesterday = date.today() - timedelta(days=1)
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CFT-1",
        date=yesterday - timedelta(days=10), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("5000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    SaleCommunication.objects.create(
        order=order,
        contacted_at=datetime.now(timezone.utc) - timedelta(days=2),
        method=SaleCommunication.Method.CALL,
        outcome=SaleCommunication.Outcome.PROMISED,
        customer_response="Заплачу в пятницу",
        promised_pay_date=yesterday,
        contacted_by=manager,
    )

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        result = promise_broken_daily_task()

    assert result == {"queued": 1}
    assert mock.call_count == 1
    text = mock.call_args.args[0]
    assert "Va'da" in text or "va'da" in text
    assert order.doc_number in text


def test_promise_broken_skips_paid_orders(
    org, m_sales, buyer, warehouse, manager,
):
    yesterday = date.today() - timedelta(days=1)
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CFT-PAID",
        date=yesterday - timedelta(days=10), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("5000000"), paid_amount_uzs=Decimal("5000000"),
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.PAID,
    )
    SaleCommunication.objects.create(
        order=order,
        contacted_at=datetime.now(timezone.utc),
        method=SaleCommunication.Method.CALL,
        outcome=SaleCommunication.Outcome.PROMISED,
        customer_response="Заплачу",
        promised_pay_date=yesterday,
        contacted_by=manager,
    )

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        result = promise_broken_daily_task()

    assert result == {"queued": 0}
    assert mock.call_count == 0


def test_promise_broken_skips_other_dates(
    org, m_sales, buyer, warehouse, manager,
):
    """promised_pay_date != yesterday → не цепляем."""
    last_week = date.today() - timedelta(days=7)
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CFT-WK",
        date=last_week, customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    SaleCommunication.objects.create(
        order=order,
        contacted_at=datetime.now(timezone.utc),
        method=SaleCommunication.Method.CALL,
        outcome=SaleCommunication.Outcome.PROMISED,
        customer_response="Заплачу",
        promised_pay_date=last_week,  # неделю назад
        contacted_by=manager,
    )

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        result = promise_broken_daily_task()

    assert result == {"queued": 0}


# ─── pre_block_warning ───────────────────────────────────────────────────


def test_pre_block_warns_when_above_70pct(
    org, m_sales, buyer, warehouse,
):
    """Долг = 7.5М, лимит = 10М (75%). Не блок (ok=True), но в жёлтой зоне."""
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-PBW-1",
        date=date.today(), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("7500000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    # max_overdue не задан, due_date в будущем — overdue блок не сработает.
    # debt 7.5M / limit 10M = 75%

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        result = pre_block_warning_daily_task()

    assert result["queued"] >= 1
    text = mock.call_args.args[0]
    assert "limit" in text.lower() or "Limit" in text
    assert "75" in text  # процент


def test_pre_block_skips_below_70pct(
    org, m_sales, buyer, warehouse,
):
    """Долг 3М / limit 10M = 30% — не пушим."""
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-PBW-LOW",
        date=date.today(), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        result = pre_block_warning_daily_task()

    # Должно быть 0 (если у других клиентов нет лимита, ничего не push)
    assert mock.call_count == 0


def test_pre_block_skips_already_blocked(
    org, m_sales, buyer, warehouse,
):
    """Уже >100% (заблокирован) — pre_block не шлёт (этим занимается debt-reminder)."""
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-PBW-OVER",
        date=date.today() - timedelta(days=10),
        customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("12000000"),  # > 10M limit
        paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )

    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        pre_block_warning_daily_task()

    assert mock.call_count == 0


# ─── debt-reminder escalation tones ──────────────────────────────────────


def test_debt_reminder_tone_pre_due(buyer):
    """До срока — мягкий тон."""
    o = SaleOrder.objects.create(
        organization=buyer.organization, module=Module.objects.get(code="sales"),
        doc_number="ПРД-T-PRE", date=date.today(), customer=buyer,
        warehouse=Warehouse.objects.create(
            organization=buyer.organization,
            module=Module.objects.get(code="sales"),
            code="СК-T1", name="t",
        ),
        amount_uzs=Decimal("1000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
        due_date=date.today() + timedelta(days=5),
    )
    text = fmt_debt_reminder_uz(o, buyer)
    assert "yaqinlashmoqda" in text.lower()


def test_debt_reminder_tone_overdue_30plus(buyer):
    """30+ дней просрочки → жёсткий тон с упоминанием блока."""
    o = SaleOrder.objects.create(
        organization=buyer.organization, module=Module.objects.get(code="sales"),
        doc_number="ПРД-T-30", date=date.today() - timedelta(days=60),
        customer=buyer,
        warehouse=Warehouse.objects.create(
            organization=buyer.organization,
            module=Module.objects.get(code="sales"),
            code="СК-T2", name="t2",
        ),
        amount_uzs=Decimal("1000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
        due_date=date.today() - timedelta(days=45),
    )
    text = fmt_debt_reminder_uz(o, buyer)
    assert "Oxirgi ogohlantirish" in text or "bloklangan" in text.lower()


def test_debt_reminder_tone_overdue_mid(buyer):
    """8-30 дней — серьёзно но не финально."""
    o = SaleOrder.objects.create(
        organization=buyer.organization, module=Module.objects.get(code="sales"),
        doc_number="ПРД-T-MID", date=date.today() - timedelta(days=20),
        customer=buyer,
        warehouse=Warehouse.objects.create(
            organization=buyer.organization,
            module=Module.objects.get(code="sales"),
            code="СК-T3", name="t3",
        ),
        amount_uzs=Decimal("1000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
        due_date=date.today() - timedelta(days=15),
    )
    text = fmt_debt_reminder_uz(o, buyer)
    assert "Jiddiy" in text or "to'xtatilishi" in text
