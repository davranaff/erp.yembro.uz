"""
Тесты ship_to_slaughter — отгрузка feedlot-партии на убой.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch
from apps.feedlot.services.ship import (
    ShipToSlaughterError,
    ship_to_slaughter,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.transfers.models import InterModuleTransfer
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def user():
    return User.objects.create(email="s@y.local", full_name="S")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "Голов"}
    )[0]


@pytest.fixture
def cat_chick(org):
    return Category.objects.get_or_create(organization=org, name="Птица живая")[0]


@pytest.fixture
def chick_nom(org, cat_chick, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Бр-01", name="Цыпленок-бройлер",
        category=cat_chick, unit=unit_pcs,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-1",
        name="Птичник-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ЛР-1",
        name="Линия разделки", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def feedlot_wh(org, m_feedlot):
    return Warehouse.objects.create(
        organization=org, module=m_feedlot, code="СК-ЖП-ФЛ", name="Склад живой птицы (откорм)"
    )


@pytest.fixture
def slaughter_wh(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter, code="СК-ЖП-УБ", name="Склад живой птицы (убой)"
    )


@pytest.fixture
def chick_batch(org, m_feedlot, feedlot_house, chick_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-ЦБ-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=feedlot_house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("15000000"),
        started_at=date(2026, 2, 1),
    )


@pytest.fixture
def feedlot_batch(org, m_feedlot, feedlot_house, chick_batch, user):
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=feedlot_house, batch=chick_batch,
        doc_number="ФЛ-001",
        placed_date=date(2026, 2, 1),
        initial_heads=10000, current_heads=9800,
        status=FeedlotBatch.Status.READY_SLAUGHTER,
        technologist=user,
    )


# ─── Core flow ───────────────────────────────────────────────────────────


def test_ship_creates_awaiting_transfer(
    feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh, chick_batch
):
    result = ship_to_slaughter(
        feedlot_batch,
        slaughter_line=slaughter_line,
        slaughter_warehouse=slaughter_wh,
        source_warehouse=feedlot_wh,
    )
    t = result.transfer
    assert t.state == InterModuleTransfer.State.AWAITING_ACCEPTANCE
    assert t.from_module_id == feedlot_batch.module_id
    assert t.to_module_id == slaughter_line.module_id
    assert t.from_block_id == feedlot_batch.house_block_id
    assert t.to_block_id == slaughter_line.id
    assert t.from_warehouse_id == feedlot_wh.id
    assert t.to_warehouse_id == slaughter_wh.id
    assert t.batch_id == chick_batch.id
    assert t.quantity == Decimal("9800")  # default — current_heads
    assert t.cost_uzs == Decimal("15000000.00")
    assert t.doc_number.startswith("ММ-")


def test_ship_updates_feedlot_status(feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh):
    ship_to_slaughter(
        feedlot_batch,
        slaughter_line=slaughter_line,
        slaughter_warehouse=slaughter_wh,
        source_warehouse=feedlot_wh,
    )
    feedlot_batch.refresh_from_db()
    assert feedlot_batch.status == FeedlotBatch.Status.SHIPPED


def test_ship_custom_quantity(
    feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh
):
    result = ship_to_slaughter(
        feedlot_batch,
        slaughter_line=slaughter_line,
        slaughter_warehouse=slaughter_wh,
        source_warehouse=feedlot_wh,
        quantity=Decimal("5000"),
    )
    assert result.transfer.quantity == Decimal("5000")


# ─── Guards ──────────────────────────────────────────────────────────────


def test_ship_already_shipped_raises(
    feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh
):
    feedlot_batch.status = FeedlotBatch.Status.SHIPPED
    feedlot_batch.save(update_fields=["status"])
    with pytest.raises(ValidationError):
        ship_to_slaughter(
            feedlot_batch,
            slaughter_line=slaughter_line,
            slaughter_warehouse=slaughter_wh,
            source_warehouse=feedlot_wh,
        )


def test_ship_withdrawal_period_blocks(
    feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh, chick_batch
):
    """Партия в каренции — нельзя отгружать на убой."""
    chick_batch.withdrawal_period_ends = date.today() + timedelta(days=5)
    chick_batch.save(update_fields=["withdrawal_period_ends"])
    with pytest.raises(ValidationError):
        ship_to_slaughter(
            feedlot_batch,
            slaughter_line=slaughter_line,
            slaughter_warehouse=slaughter_wh,
            source_warehouse=feedlot_wh,
        )


def test_ship_slaughter_line_wrong_module_raises(
    feedlot_batch, slaughter_wh, feedlot_wh, feedlot_house
):
    # Передадим feedlot-блок вместо slaughter_line
    with pytest.raises(ValidationError):
        ship_to_slaughter(
            feedlot_batch,
            slaughter_line=feedlot_house,
            slaughter_warehouse=slaughter_wh,
            source_warehouse=feedlot_wh,
        )


def test_ship_source_warehouse_wrong_module_raises(
    feedlot_batch, slaughter_line, slaughter_wh
):
    with pytest.raises(ValidationError):
        ship_to_slaughter(
            feedlot_batch,
            slaughter_line=slaughter_line,
            slaughter_warehouse=slaughter_wh,
            source_warehouse=slaughter_wh,  # из slaughter, а не feedlot
        )


def test_ship_zero_quantity_raises(
    feedlot_batch, slaughter_line, slaughter_wh, feedlot_wh
):
    with pytest.raises(ValidationError):
        ship_to_slaughter(
            feedlot_batch,
            slaughter_line=slaughter_line,
            slaughter_warehouse=slaughter_wh,
            source_warehouse=feedlot_wh,
            quantity=Decimal("0"),
        )
