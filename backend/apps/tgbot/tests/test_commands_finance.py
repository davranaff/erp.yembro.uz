"""
Финансовые команды: /cash /debt /pnl /sales — на минимальных DB-фикстурах.
Проверяем что хендлеры не падают и структура текста корректна.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.tgbot.dispatcher import dispatch_message


pytestmark = pytest.mark.django_db


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


def test_cash_command_renders(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/cash"))
    text = fake_send.calls[0][1]
    # Узбекский после B-рефактора: «Kassa va bank» / «Jami»
    assert "Kassa va bank" in text
    assert "Jami" in text


def test_debt_command_empty_state(tg_link, fake_send):
    """Если нет неоплаченных заказов — выводится «Barcha sotuvlar to'langan»."""
    dispatch_message(_msg(tg_link.chat_id, "/debt"))
    text = fake_send.calls[0][1]
    # Заголовок переведён на узбекский в B-refactor
    assert "Mijoz qarzlari" in text
    assert "to'langan" in text.lower()


def test_debt_command_lists_top_debtor(tg_link, fake_send, org):
    from apps.counterparties.models import Counterparty
    from apps.modules.models import Module
    from apps.sales.models import SaleOrder
    from apps.warehouses.models import Warehouse

    cp = Counterparty.objects.create(
        organization=org, code="К-DEBT", kind="buyer", name="Должник 1",
    )
    wh = Warehouse.objects.create(
        organization=org, module=Module.objects.get(code="vet"),
        code="СК-DEBT", name="СкДолг",
    )
    SaleOrder.objects.create(
        organization=org, module=Module.objects.get(code="vet"),
        doc_number="ПР-DEBT-1", date=date.today() - timedelta(days=20),
        customer=cp, warehouse=wh,
        amount_uzs=Decimal("10000000"),
        paid_amount_uzs=Decimal("0"),
        status=SaleOrder.Status.CONFIRMED,
        payment_status=SaleOrder.PaymentStatus.UNPAID,
        due_date=date.today() - timedelta(days=10),
    )
    dispatch_message(_msg(tg_link.chat_id, "/debt"))
    text = fake_send.calls[0][1]
    assert "Должник 1" in text
    assert "ПР-DEBT-1" in text
    # «kechikkan» — узбекский эквивалент «просрочка/опоздал»
    assert "kechikkan" in text.lower()


def test_pnl_command_renders_for_week(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/pnl week"))
    text = fake_send.calls[0][1]
    # «&amp;» из-за HTML-эскейпа в "P&L"
    assert "P&amp;L" in text or "P&L" in text
    assert "Доходы" in text and "Расходы" in text and "Прибыль" in text


def test_sales_command_empty_state(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/sales today"))
    text = fake_send.calls[0][1]
    # Узбекский после B-refactor
    assert "Sotuvlar" in text
    assert "Hujjatlar:" in text


# ─── /cred — регрессия на FieldError(supplier→counterparty) ─────────────


def test_cred_callback_renders_without_crash(tg_link, fake_send, org):
    """Регрессия: PurchaseOrder.supplier не существует — было FieldError.
    Поле называется counterparty. Колбек не должен падать."""
    from apps.tgbot.dispatcher import dispatch_callback
    dispatch_callback({
        "id": "cbq-cred",
        "data": "fin:cred",
        "message": {"chat": {"id": tg_link.chat_id}, "message_id": 42},
    })
    all_text = " ".join(t for _, _, t, _ in fake_send.edits) + " ".join(
        t for _, t, _ in fake_send.calls
    )
    # Узбекский: «Yetkazib beruvchi qarzlari»
    assert "Yetkazib beruvchi" in all_text
    # Не падает = главное; пустой БД отдаст «Barcha xaridlar to'langan».


def test_debt_pagination_navigates_pages(tg_link, fake_send, org):
    """12 неоплаченных продаж → 1-я страница 10, 2-я 2 + кнопки навигации."""
    from apps.counterparties.models import Counterparty
    from apps.modules.models import Module
    from apps.sales.models import SaleOrder
    from apps.warehouses.models import Warehouse

    cp = Counterparty.objects.create(
        organization=org, code="К-PAGE", kind="buyer", name="Page test",
    )
    m_vet = Module.objects.get(code="vet")
    wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-PAGE", name="Скл",
    )
    for i in range(12):
        SaleOrder.objects.create(
            organization=org, module=m_vet,
            doc_number=f"ПР-PG-{i:02d}", date=date.today(),
            customer=cp, warehouse=wh,
            amount_uzs=Decimal(str(1_000_000 * (12 - i))),  # decreasing
            paid_amount_uzs=Decimal("0"),
            status=SaleOrder.Status.CONFIRMED,
            payment_status=SaleOrder.PaymentStatus.UNPAID,
        )

    # Page 1
    from apps.tgbot.dispatcher import dispatch_callback
    dispatch_callback({
        "id": "cbq-page1", "data": "fin:debt",
        "message": {"chat": {"id": tg_link.chat_id}, "message_id": 1},
    })
    text1 = fake_send.edits[-1][2]
    markup1 = fake_send.edits[-1][3]
    assert "Jami 12 ta hujjat" in text1
    # Должно быть 10 строк (1.-10.)
    for i in range(1, 11):
        assert f"\n{i}. " in text1
    # Должна быть кнопка «Keyingi →» с callback fin:debt:2
    callbacks = {b["callback_data"] for row in markup1["inline_keyboard"] for b in row}
    assert "fin:debt:2" in callbacks
    # И не должно быть «← Oldingi» (мы на 1-й)
    assert "fin:debt:0" not in callbacks

    # Page 2
    fake_send.edits.clear()
    dispatch_callback({
        "id": "cbq-page2", "data": "fin:debt:2",
        "message": {"chat": {"id": tg_link.chat_id}, "message_id": 1},
    })
    text2 = fake_send.edits[-1][2]
    markup2 = fake_send.edits[-1][3]
    # На второй стр элементы 11 и 12
    assert "\n11. " in text2
    assert "\n12. " in text2
    # Должна быть «← Oldingi» (вернуться на 1)
    callbacks2 = {b["callback_data"] for row in markup2["inline_keyboard"] for b in row}
    assert "fin:debt:1" in callbacks2


def test_cred_callback_lists_top_supplier(tg_link, fake_send, org):
    from apps.counterparties.models import Counterparty
    from apps.modules.models import Module
    from apps.purchases.models import PurchaseOrder
    from apps.warehouses.models import Warehouse

    m_vet = Module.objects.get(code="vet")
    cp = Counterparty.objects.create(
        organization=org, code="К-CRED", kind="supplier", name="Поставщик-CRED",
    )
    wh = Warehouse.objects.create(
        organization=org, module=m_vet, code="СК-CRED", name="Скл CRED",
    )
    PurchaseOrder.objects.create(
        organization=org, module=m_vet,
        doc_number="ПЛ-CRED-1", date=date.today(),
        counterparty=cp, warehouse=wh,
        amount_uzs=Decimal("12000000"),
        paid_amount_uzs=Decimal("0"),
        status=PurchaseOrder.Status.CONFIRMED,
        payment_status=PurchaseOrder.PaymentStatus.UNPAID,
    )
    from apps.tgbot.dispatcher import dispatch_callback
    dispatch_callback({
        "id": "cbq-cred-2",
        "data": "fin:cred",
        "message": {"chat": {"id": tg_link.chat_id}, "message_id": 99},
    })
    all_text = " ".join(t for _, _, t, _ in fake_send.edits) + " ".join(
        t for _, t, _ in fake_send.calls
    )
    assert "Поставщик-CRED" in all_text
    assert "ПЛ-CRED-1" in all_text
