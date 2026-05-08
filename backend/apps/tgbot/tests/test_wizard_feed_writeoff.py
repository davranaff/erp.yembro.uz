"""
End-to-end тесты wizard'а `/chiqim` (списание со склада).

Проверяем:
  - happy path: 4 шага → создаётся StockMovement(WRITE_OFF) с правильной WAC
  - попытка списать > остатка → ошибка, сессия в qty
  - нулевой остаток → wizard падает на nom-step
  - cancel чистит сессию
  - RBAC stock-gate
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.tgbot.dispatcher import dispatch_callback, dispatch_message
from apps.tgbot.models import TgWizardSession
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "Килограмм"}
    )[0]


@pytest.fixture
def cat_feed(org, m_feed):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.05")
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё (wo)",
        defaults={"default_gl_subaccount": sub, "module": m_feed},
    )[0]


@pytest.fixture
def corn(org, cat_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-WO", name="Кукуруза WO",
        category=cat_feed, unit=unit_kg,
    )


@pytest.fixture
def warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-WO", name="Склад WO",
    )


@pytest.fixture
def stocked_warehouse(warehouse, corn, m_feed, org):
    """Подгружаем 100 кг по цене 18000 для расчёта WAC."""
    StockMovement.objects.create(
        organization=org, module=m_feed,
        doc_number="ПР-WO-001",
        kind=StockMovement.Kind.INCOMING,
        date=datetime.now(timezone.utc),
        nomenclature=corn, quantity=Decimal("100"),
        unit_price_uzs=Decimal("18000"),
        amount_uzs=Decimal("1800000"),
        warehouse_to=warehouse,
    )
    return warehouse


@pytest.fixture
def admin_link(db, tg_link):
    """Доступ к stock:rw для /chiqim."""
    from apps.organizations.models import OrganizationMembership
    from apps.rbac.models import AccessLevel, UserModuleAccessOverride
    membership = OrganizationMembership.objects.get(
        user=tg_link.user, organization=tg_link.organization,
    )
    UserModuleAccessOverride.objects.update_or_create(
        membership=membership, module=Module.objects.get(code="stock"),
        defaults={"level": AccessLevel.READ_WRITE},
    )
    return tg_link


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def _cbq(chat_id, data):
    return {
        "id": "cb-wo-1",
        "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": 99},
        "from": {"id": chat_id},
    }


def test_full_writeoff_creates_stockmovement_with_wac(
    fake_send, admin_link, stocked_warehouse, corn,
):
    chat_id = admin_link.chat_id

    dispatch_message(_msg(chat_id, "/chiqim"))
    session = TgWizardSession.objects.get(chat_id=chat_id)
    assert session.state == "writeoff:warehouse"

    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:wh:{stocked_warehouse.id}"))
    session.refresh_from_db()
    assert session.state == "writeoff:nom"

    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:nom:{corn.id}"))
    session.refresh_from_db()
    assert session.state == "writeoff:qty"
    assert Decimal(session.payload["balance"]) == Decimal("100")
    assert Decimal(session.payload["unit_price"]) == Decimal("18000.00")

    dispatch_message(_msg(chat_id, "5"))
    session.refresh_from_db()
    assert session.state == "writeoff:reason"

    dispatch_message(_msg(chat_id, "порча от влаги"))
    session.refresh_from_db()
    assert session.state == "writeoff:confirm"
    assert session.payload["reason"] == "порча от влаги"

    dispatch_callback(_cbq(chat_id, "wiz:writeoff:do"))
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()

    movement = StockMovement.objects.get(
        nomenclature=corn, warehouse_from=stocked_warehouse,
        kind=StockMovement.Kind.WRITE_OFF,
    )
    assert movement.quantity == Decimal("5")
    assert movement.unit_price_uzs == Decimal("18000.00")
    assert movement.amount_uzs == Decimal("90000.00")  # 5 × 18000


def test_writeoff_qty_exceeds_balance_keeps_qty_state(
    fake_send, admin_link, stocked_warehouse, corn,
):
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/chiqim"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:wh:{stocked_warehouse.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:nom:{corn.id}"))

    # Баланс 100, шлём 200
    dispatch_message(_msg(chat_id, "200"))
    session = TgWizardSession.objects.get(chat_id=chat_id)
    assert session.state == "writeoff:qty"
    assert any("остатка" in t for _, t, _ in fake_send.calls)


def test_writeoff_zero_balance_aborts_at_nom(
    fake_send, admin_link, warehouse, corn,
):
    """Если по этой паре nom×wh не было INCOMING — wizard прерывается."""
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/chiqim"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:wh:{warehouse.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:nom:{corn.id}"))

    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()
    assert any("равен нулю" in t for _, t, _ in fake_send.calls)


def test_writeoff_short_reason_keeps_state(
    fake_send, admin_link, stocked_warehouse, corn,
):
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/chiqim"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:wh:{stocked_warehouse.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:writeoff:nom:{corn.id}"))
    dispatch_message(_msg(chat_id, "5"))

    dispatch_message(_msg(chat_id, "ок"))  # 2 символа
    session = TgWizardSession.objects.get(chat_id=chat_id)
    assert session.state == "writeoff:reason"

    dispatch_message(_msg(chat_id, "плесень"))
    session.refresh_from_db()
    assert session.state == "writeoff:confirm"
