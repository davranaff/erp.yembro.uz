"""
End-to-end тесты wizard'а `/qabul` (приход на склад).

Гоняем dispatcher вживую: имитируем сообщения и callback'и от Telegram,
проверяем что в результате создан PurchaseOrder + StockMovement(INCOMING)
+ JournalEntry. Под капотом wizard вызывает реальный `confirm_purchase`,
поэтому если сломается основная закупка — тест упадёт.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.accounting.models import GLSubaccount
from apps.counterparties.models import Counterparty
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.purchases.models import PurchaseOrder
from apps.tgbot.dispatcher import dispatch_callback, dispatch_message
from apps.tgbot.models import TgWizardSession
from apps.warehouses.models import StockMovement, Warehouse


pytestmark = pytest.mark.django_db


# ─── Fixtures ────────────────────────────────────────────────────────────


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
        organization=org, name="Корма сырьё (wiz)",
        defaults={"default_gl_subaccount": sub, "module": m_feed},
    )[0]


@pytest.fixture
def corn(org, cat_feed, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-WIZ", name="Кукуруза WIZ",
        category=cat_feed, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-SUPP-WIZ", kind="supplier", name="Агроимпорт WIZ",
    )


@pytest.fixture
def warehouse(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-СР-WIZ", name="Склад сырья WIZ",
    )


@pytest.fixture
def admin_link(db, org, tg_link):
    """Подгрузим RBAC доступ purchases:rw для admin-link, чтобы /qabul прошёл RBAC-gate."""
    from apps.rbac.models import AccessLevel, UserModuleAccessOverride
    from apps.organizations.models import OrganizationMembership
    membership = OrganizationMembership.objects.get(
        user=tg_link.user, organization=tg_link.organization,
    )
    UserModuleAccessOverride.objects.update_or_create(
        membership=membership, module=Module.objects.get(code="purchases"),
        defaults={"level": AccessLevel.READ_WRITE},
    )
    return tg_link


def _msg(chat_id: int, text: str) -> dict:
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def _cbq(chat_id: int, data: str) -> dict:
    return {
        "id": "cb-test-1",
        "data": data,
        "message": {"chat": {"id": chat_id}, "message_id": 42},
        "from": {"id": chat_id},
    }


# ─── Tests ──────────────────────────────────────────────────────────────


def test_full_purchase_wizard_creates_confirmed_order(
    fake_send, admin_link, warehouse, supplier, corn, org,
):
    """Пройдём все 5 шагов и проверим что закуп проведён."""
    chat_id = admin_link.chat_id

    # 1. /qabul → создаёт сессию, шлёт список складов
    dispatch_message(_msg(chat_id, "/qabul"))
    session = TgWizardSession.objects.get(chat_id=chat_id)
    assert session.wizard == "feed_purchase"
    assert session.state == "purchase:warehouse"

    # 2. Выбор склада
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:wh:{warehouse.id}"))
    session.refresh_from_db()
    assert session.state == "purchase:supplier"
    assert session.payload["warehouse_id"] == str(warehouse.id)

    # 3. Выбор поставщика
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:sup:{supplier.id}"))
    session.refresh_from_db()
    assert session.state == "purchase:nom"
    assert session.payload["supplier_id"] == str(supplier.id)

    # 4. Выбор номенклатуры
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:nom:{corn.id}"))
    session.refresh_from_db()
    assert session.state == "purchase:qty"

    # 5. Ввод количества (текст, поглощается wizard'ом)
    dispatch_message(_msg(chat_id, "500"))
    session.refresh_from_db()
    assert session.state == "purchase:price"
    assert Decimal(session.payload["quantity"]) == Decimal("500")

    # 6. Ввод цены
    dispatch_message(_msg(chat_id, "18000"))
    session.refresh_from_db()
    assert session.state == "purchase:confirm"
    assert Decimal(session.payload["price"]) == Decimal("18000")

    # 7. Подтверждение → confirm_purchase
    dispatch_callback(_cbq(chat_id, "wiz:purchase:do"))

    # Сессия должна быть удалена
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()

    # PurchaseOrder создан и проведён
    order = PurchaseOrder.objects.get(
        counterparty=supplier, warehouse=warehouse,
    )
    assert order.status == PurchaseOrder.Status.CONFIRMED
    assert order.amount_uzs == Decimal("9000000.00")  # 500 * 18000
    # StockMovement INCOMING создан
    assert StockMovement.objects.filter(
        nomenclature=corn, warehouse_to=warehouse,
        kind=StockMovement.Kind.INCOMING, quantity=Decimal("500"),
    ).exists()


def test_cancel_button_clears_session(
    fake_send, admin_link, warehouse, supplier, corn,
):
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/qabul"))
    assert TgWizardSession.objects.filter(chat_id=chat_id).exists()

    dispatch_callback(_cbq(chat_id, "wiz:purchase:cancel"))
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()


def test_invalid_qty_keeps_session_in_qty_state(
    fake_send, admin_link, warehouse, supplier, corn,
):
    """Невалидный qty → сессия остаётся в qty, юзер вводит снова."""
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/qabul"))
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:wh:{warehouse.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:sup:{supplier.id}"))
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:nom:{corn.id}"))

    # Шлём не-число
    dispatch_message(_msg(chat_id, "сколько-то"))
    session = TgWizardSession.objects.get(chat_id=chat_id)
    assert session.state == "purchase:qty"

    # Шлём 0 — тоже не валидно
    dispatch_message(_msg(chat_id, "0"))
    session.refresh_from_db()
    assert session.state == "purchase:qty"

    # Корректный qty → переходим к price
    dispatch_message(_msg(chat_id, "100"))
    session.refresh_from_db()
    assert session.state == "purchase:price"


def test_bekor_command_cancels_running_wizard(
    fake_send, admin_link, warehouse, supplier,
):
    """`/bekor` посреди wizard'а должен снести сессию."""
    chat_id = admin_link.chat_id
    dispatch_message(_msg(chat_id, "/qabul"))
    dispatch_callback(_cbq(chat_id, f"wiz:purchase:wh:{warehouse.id}"))
    assert TgWizardSession.objects.filter(chat_id=chat_id).exists()

    dispatch_message(_msg(chat_id, "/bekor"))
    assert not TgWizardSession.objects.filter(chat_id=chat_id).exists()


def test_qabul_blocked_without_purchases_module(fake_send, tg_link):
    """Юзер без purchases:r → команда отбита RBAC-gate."""
    from apps.modules.models import Module
    from apps.rbac.models import UserModuleAccessOverride
    from apps.organizations.models import OrganizationMembership
    membership = OrganizationMembership.objects.get(
        user=tg_link.user, organization=tg_link.organization,
    )
    UserModuleAccessOverride.objects.filter(
        membership=membership, module=Module.objects.get(code="purchases"),
    ).delete()

    dispatch_message(_msg(tg_link.chat_id, "/qabul"))
    assert any("ruxsat yo'q" in t for _, t, _ in fake_send.calls)
    assert not TgWizardSession.objects.filter(chat_id=tg_link.chat_id).exists()
