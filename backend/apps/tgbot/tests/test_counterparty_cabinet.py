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
    # Первое сообщение — приветствие + inline-меню; второе (опц) — reply_kb hint.
    welcome = sent[0]
    _, text, markup = welcome
    assert "Mijoz X" in text or "Salom" in text
    callbacks = {
        b["callback_data"]
        for row in markup["inline_keyboard"]
        for b in row
    }
    assert "cp:orders" in callbacks
    assert "cp:debt" in callbacks
    assert "cp:holat" in callbacks
    # И постоянная reply-клавиатура для быстрой навигации
    if len(sent) > 1:
        _, _, kb = sent[-1]
        assert "keyboard" in kb  # ReplyKeyboardMarkup


def test_cp_reply_button_text_routes_to_command(cp_link, fake_send):
    """Юзер тапает кнопку «📦 Buyurtmalarim» (reply_kb) → текст шлётся
    как обычное сообщение → dispatcher преобразует в /buyurtmalar и
    вызывает handler."""
    dispatch_message(_msg(cp_link.chat_id, "📦 Buyurtmalarim"))
    text = fake_send.calls[-1][1]
    # Должно открыться окно «Buyurtmalaringiz» (как от /buyurtmalar)
    assert "Buyurtmalar" in text


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
    assert "to'lanmagan buyurtmalar yo'q" in text.lower()


def test_cp_holat_active_when_under_limit(cp_link, fake_send):
    """Без долгов и в пределах лимита — статус «faol»."""
    dispatch_message(_msg(cp_link.chat_id, "/holat"))
    text = fake_send.calls[-1][1]
    assert "faol" in text.lower()


def test_cp_holat_shows_real_debt_when_no_credit_limit_set(
    org, m_sales, warehouse, fake_send,
):
    """Регрессия: клиент БЕЗ credit_limit_uzs/max_overdue_days. У него
    есть реальный долг 24M (из confirmed-неоплаченной продажи). Бот должен
    показать актуальный долг, а не 0 (раньше fast-path в check_customer_credit
    возвращал 0 для клиентов без лимитов)."""
    cp_no_limit = Counterparty.objects.create(
        organization=org, code="К-NOLIM", kind="buyer", name="Без лимита",
        # credit_limit_uzs=None, max_overdue_days=None — defaults
    )
    SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-NL-1",
        date=date(2026, 4, 1), customer=cp_no_limit, warehouse=warehouse,
        amount_uzs=Decimal("24000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    cp_link2 = TgLink.objects.create(
        organization=org, counterparty=cp_no_limit,
        chat_id=606060, is_active=True,
    )
    dispatch_message(_msg(cp_link2.chat_id, "/holat"))
    text = fake_send.calls[-1][1]
    # Должен показать 24 000 000 (а не 0)
    assert "24 000 000" in text
    # Статус всё равно faol (лимит не задан → не блокировка), но с
    # предупреждением что долг есть
    assert "faol" in text.lower()


def test_cp_order_drill_down_shows_items_and_payments(
    cp_link, buyer, org, m_sales, warehouse, fake_send,
):
    """Клик по конкретному заказу → детали с позициями + история платежей."""
    from apps.nomenclature.models import Category, NomenclatureItem, Unit
    unit, _ = Unit.objects.get_or_create(
        organization=org, code="kg", defaults={"name": "kg"},
    )
    cat, _ = Category.objects.get_or_create(
        organization=org, name="Test cat for drill",
    )
    nom = NomenclatureItem.objects.create(
        organization=org, sku="TEST-DRILL", name="Test product",
        category=cat, unit=unit,
    )
    order = SaleOrder.objects.create(
        organization=org, module=m_sales, doc_number="ПРД-DRILL",
        date=date(2026, 5, 1), customer=buyer, warehouse=warehouse,
        amount_uzs=Decimal("3000000"), paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
    )
    from apps.sales.models import SaleItem
    SaleItem.objects.create(
        order=order, nomenclature=nom,
        quantity=Decimal("100"), unit_price_uzs=Decimal("30000"),
        line_total_uzs=Decimal("3000000"),
    )

    # Эмулируем callback drill-down
    from apps.tgbot.dispatcher import dispatch_callback
    dispatch_callback({
        "id": "cbq-drill", "data": f"cp:order:{order.id}",
        "message": {"chat": {"id": cp_link.chat_id}, "message_id": 1},
    })
    # Текст в edits (callback редактирует in-place)
    edits_text = "\n".join(t for _, _, t, _ in fake_send.edits)
    assert "ПРД-DRILL" in edits_text
    assert "Test product" in edits_text
    assert "3 000 000" in edits_text


def test_cp_catalog_shows_available_products(
    cp_link, org, m_sales, fake_send,
):
    """/mahsulotlar показывает доступные товары: вет-аксессуары, корм, и т.д."""
    from apps.modules.models import Module
    from apps.nomenclature.models import Category, NomenclatureItem, Unit
    from apps.vet.models import VetAccessory
    from apps.warehouses.models import Warehouse

    m_vet = Module.objects.get(code="vet")
    cat, _c = Category.objects.get_or_create(
        organization=org, name="Cat-cat",
    )
    unit, _u = Unit.objects.get_or_create(
        organization=org, code="cat-unit", defaults={"name": "u"},
    )
    nom = NomenclatureItem.objects.create(
        organization=org, sku="CAT-1", name="Test Drug",
        category=cat, unit=unit,
    )
    wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-CAT", name="WH",
    )
    VetAccessory.objects.create(
        organization=org, module=m_vet, nomenclature=nom, warehouse=wh,
        current_quantity=Decimal("50"),
        cost_per_unit_uzs=Decimal("100"), sale_price_uzs=Decimal("200"),
        is_active=True,
    )

    dispatch_message(_msg(cp_link.chat_id, "/mahsulotlar"))
    text = fake_send.calls[-1][1]
    assert "Test Drug" in text
    assert "50" in text  # количество
    assert "katalog" in text.lower()


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
