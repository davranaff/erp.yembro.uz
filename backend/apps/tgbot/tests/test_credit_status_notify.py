"""
Тесты notify_credit_status_change: если кредит-статус клиента изменился
(was_ok != is_ok), он получает push-уведомление в TG. Если не изменился —
ничего не шлём (без шума).
"""
from unittest.mock import patch

import pytest

from apps.counterparties.models import Counterparty
from apps.organizations.models import Organization
from apps.tgbot.models import TgLink
from apps.tgbot.services.orchestration import notify_credit_status_change


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def buyer(org):
    return Counterparty.objects.create(
        organization=org, code="К-CRED-N", kind="buyer", name="Buyer",
    )


@pytest.fixture
def cp_link(org, buyer):
    return TgLink.objects.create(
        organization=org, counterparty=buyer, chat_id=909090, is_active=True,
    )


def test_notify_when_just_blocked(buyer, cp_link):
    """was_ok=True → is_ok=False → клиент получает «bloklangan» push."""
    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        notify_credit_status_change(
            buyer, was_ok=True, is_ok=False,
            reasons=["Превышен лимит на 5М"],
        )
    assert mock.call_count == 1
    text = mock.call_args.args[0]
    assert "bloklangan" in text.lower()
    assert "Превышен лимит" in text


def test_notify_when_just_unblocked(buyer, cp_link):
    """was_ok=False → is_ok=True → клиент получает «qayta faol» push."""
    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        notify_credit_status_change(buyer, was_ok=False, is_ok=True)
    assert mock.call_count == 1
    text = mock.call_args.args[0]
    assert "faol" in text.lower()


def test_no_notify_when_status_same(buyer, cp_link):
    """was_ok==is_ok → нет уведомления (без шума)."""
    with patch("apps.tgbot.tasks.notify_counterparty_task.delay") as mock:
        notify_credit_status_change(buyer, was_ok=True, is_ok=True)
        notify_credit_status_change(buyer, was_ok=False, is_ok=False)
    assert mock.call_count == 0
