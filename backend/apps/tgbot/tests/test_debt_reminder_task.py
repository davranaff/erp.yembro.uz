"""
Регрессия: send_debt_reminder_task должен работать с SaleOrder.customer
(а не несуществующим .counterparty). Раньше падал с FieldError на
select_related, daily reminders молча не доходили никому из должников.
"""
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.sales.models import SaleOrder
from apps.tgbot.models import TgLink
from apps.tgbot.tasks import send_debt_reminder_task


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
        organization=org, code="К-DBT", kind="buyer", name="Должник",
    )


@pytest.fixture
def warehouse(org, m_sales):
    from apps.warehouses.models import Warehouse
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-DBT", name="Sales WH",
    )


def test_debt_reminder_sends_to_linked_counterparty(org, m_sales, buyer, warehouse):
    """Если у клиента есть TgLink — напоминание уходит в его чат."""
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-DBT-1",
        date=date(2026, 5, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("500000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    TgLink.objects.create(
        organization=org, counterparty=buyer, chat_id=7777, is_active=True,
    )

    with patch("apps.tgbot.bot.send_message") as mock_send:
        mock_send.return_value = True
        result = send_debt_reminder_task(str(order.id))

    assert result == {"sent": True, "chat_id": 7777}
    mock_send.assert_called_once()


def test_debt_reminder_no_link_returns_error(org, m_sales, buyer, warehouse):
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-DBT-2",
        date=date(2026, 5, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("100000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    result = send_debt_reminder_task(str(order.id))
    assert result == {"error": "no_tg_link", "order": str(order.id)}
