"""
Тесты клиент-кабинета: dispatcher впускает cp-link, /menu отдаёт другую
структуру, /buyurtmalar / /qarz / /holat возвращают данные scope'нутые
к этому контрагенту.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.sales.models import SaleOrder
from apps.tgbot.dispatcher import dispatch_message
from apps.tgbot.models import TgLink
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
        organization=org, code="К-CP", kind="buyer", name="Mijoz X",
        credit_limit_uzs=Decimal("10000000"),
    )


@pytest.fixture
def cp_link(org, buyer):
    return TgLink.objects.create(
        organization=org, counterparty=buyer, chat_id=505050, is_active=True,
    )


@pytest.fixture
def warehouse(org, m_sales):
    return Warehouse.objects.create(
        organization=org, module=m_sales, code="СК-CP", name="Sales WH",
    )


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def test_cp_link_can_open_menu(cp_link, fake_send):
    """/menu для cp-link должен отрисовать клиент-кабинет (Buyurtmalarim/Qarz/Holat)."""
    dispatch_message(_msg(cp_link.chat_id, "/menu"))
    sent = fake_send.calls
    assert sent
    _, text, markup = sent[-1]
    assert "Mijoz X" in text or "Salom" in text
    callbacks = {
        b["callback_data"]
        for row in markup["inline_keyboard"]
        for b in row
    }
    assert "cp:orders" in callbacks
    assert "cp:debt" in callbacks
    assert "cp:holat" in callbacks


def test_cp_link_blocked_from_admin_command(cp_link, fake_send):
    """cp-link не может звать admin-команду /pnl — audience-gate отбивает."""
    dispatch_message(_msg(cp_link.chat_id, "/pnl"))
    assert any("xodimlar" in t.lower() for _, t, _ in fake_send.calls)


def test_cp_orders_lists_my_orders_with_debt(
    cp_link, buyer, org, m_sales, warehouse, fake_send,
):
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CP-1",
        date=date(2026, 5, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("5000000"), paid_amount_uzs=Decimal("1000000"),
        status=SaleOrder.Status.CONFIRMED,
        due_date=date(2026, 5, 10),
    )
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CP-2",
        date=date(2026, 4, 20), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("2000000"), paid_amount_uzs=Decimal("2000000"),
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.PAID,
    )

    dispatch_message(_msg(cp_link.chat_id, "/buyurtmalar"))
    text = fake_send.calls[-1][1]
    assert "ПРД-CP-1" in text
    assert "ПРД-CP-2" in text
    # Долг по первому
    assert "4 000 000" in text  # 5М - 1М
    # Полностью оплачен второй
    assert "to'liq" in text.lower()


def test_cp_qarz_shows_total_debt(
    cp_link, buyer, org, m_sales, warehouse, fake_send,
):
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CP-3",
        date=date(2026, 5, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    dispatch_message(_msg(cp_link.chat_id, "/qarz"))
    text = fake_send.calls[-1][1]
    assert "3 000 000" in text
    assert "qarzdorlig" in text.lower()


def test_cp_qarz_when_no_debt(cp_link, fake_send):
    dispatch_message(_msg(cp_link.chat_id, "/qarz"))
    text = fake_send.calls[-1][1]
    assert "qarzdorlik yo'q" in text.lower() or "rahmat" in text.lower()


def test_cp_holat_active_when_under_limit(cp_link, fake_send):
    """Без долгов и в пределах лимита — статус «faol»."""
    dispatch_message(_msg(cp_link.chat_id, "/holat"))
    text = fake_send.calls[-1][1]
    assert "faol" in text.lower()


def test_cp_holat_blocked_when_over_limit(
    cp_link, buyer, org, m_sales, warehouse, fake_send,
):
    """Превышен лимит → статус «bloklangan»."""
    # credit_limit = 10M, делаем долг 12M
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-CP-OVER",
        date=date(2026, 4, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("12000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
        due_date=date(2026, 4, 10),  # просрочка
    )
    # Также установим max_overdue_days чтобы тест не зависел только от
    # лимита — сторно overdue-ветки.
    buyer.max_overdue_days = 5
    buyer.save()

    dispatch_message(_msg(cp_link.chat_id, "/holat"))
    text = fake_send.calls[-1][1]
    assert "bloklangan" in text.lower()
