"""
Production команды: /feedlot /batch /herd.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.tgbot.dispatcher import dispatch_message


pytestmark = pytest.mark.django_db


def _msg(chat_id, text):
    return {"chat": {"id": chat_id}, "text": text, "from": {"id": chat_id}}


@pytest.fixture
def feedlot_batch(db, org):
    """Минимальный feedlot batch с парт-родителем."""
    from apps.batches.models import Batch
    from apps.feedlot.models import FeedlotBatch
    from apps.modules.models import Module
    from apps.nomenclature.models import Category, NomenclatureItem, Unit
    from apps.users.models import User
    from apps.warehouses.models import ProductionBlock

    m_feedlot = Module.objects.get(code="feedlot")
    unit = Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "Голов"}
    )[0]
    cat = Category.objects.get_or_create(organization=org, name="Птица TG")[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="TG-БР-1", name="Бройлер TG",
        category=cat, unit=unit,
    )
    house = ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-TG-1",
        name="Птичник TG", kind=ProductionBlock.Kind.FEEDLOT,
    )
    parent = Batch.objects.create(
        organization=org, doc_number="П-TG-1",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("9500"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date.today() - timedelta(days=20),
    )
    user = User.objects.create(email="techtg@y.local", full_name="Tech TG")
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=house, batch=parent,
        doc_number="ФЛ-TG-1", placed_date=date.today() - timedelta(days=20),
        target_weight_kg=Decimal("2.500"),
        initial_heads=10000, current_heads=9500,
        status=FeedlotBatch.Status.GROWING,
        technologist=user,
    )


def test_feedlot_command_lists_active(tg_link, fake_send, feedlot_batch):
    dispatch_message(_msg(tg_link.chat_id, "/feedlot"))
    text = fake_send.calls[0][1]
    assert "Активные партии" in text
    assert "ФЛ-TG-1" in text


def test_batch_command_unknown_doc(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/batch UNKNOWN-DOC"))
    text = fake_send.calls[0][1]
    assert "не найдена" in text


def test_batch_command_renders_card(tg_link, fake_send, feedlot_batch):
    dispatch_message(_msg(tg_link.chat_id, "/batch П-TG-1"))
    text = fake_send.calls[0][1]
    assert "П-TG-1" in text
    assert "Накопленная себестоимость" in text


def test_batch_command_no_args_shows_usage(tg_link, fake_send):
    dispatch_message(_msg(tg_link.chat_id, "/batch"))
    text = fake_send.calls[0][1]
    assert "Использование" in text
