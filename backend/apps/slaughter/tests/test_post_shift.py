"""
Тесты post_slaughter_shift.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import JournalEntry
from apps.batches.models import Batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import (
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)
from apps.slaughter.services.post_shift import (
    SlaughterPostError,
    post_slaughter_shift,
)
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, StockMovement, Warehouse


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
    return User.objects.create(email="foreman@y.local", full_name="Foreman")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "кг"}
    )[0]


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "шт"}
    )[0]


@pytest.fixture
def cat_live(org):
    return Category.objects.get_or_create(
        organization=org, name="Птица живая"
    )[0]


@pytest.fixture
def cat_fg(org):
    return Category.objects.get_or_create(
        organization=org, name="Готовая продукция"
    )[0]


@pytest.fixture
def chick_nom(org, cat_live, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Сут-01", name="Цыпленок",
        category=cat_live, unit=unit_pcs,
    )


@pytest.fixture
def tushka_nom(org, cat_fg, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ГП-Туш-01", name="Тушка",
        category=cat_fg, unit=unit_kg,
    )


@pytest.fixture
def grudka_nom(org, cat_fg, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ГП-Гр-01", name="Грудка",
        category=cat_fg, unit=unit_kg,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="А-1",
        name="А-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ЛН-1",
        name="Линия", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def feedlot_wh(org, m_feedlot):
    return Warehouse.objects.create(
        organization=org, module=m_feedlot, code="СК-Ф", name="СкФ"
    )


@pytest.fixture
def slaughter_fg_wh(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter, code="СК-ГП", name="СкГП"
    )


@pytest.fixture
def birds_batch(
    org, m_feedlot, m_slaughter, feedlot_house, slaughter_line,
    chick_nom, unit_pcs,
):
    """Партия принята в slaughter (current_module=slaughter после accept_transfer)."""
    return Batch.objects.create(
        organization=org, doc_number="П-BIRDS-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_slaughter,
        current_block=slaughter_line,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("10000000.00"),  # 10М накоплено
        started_at=date.today(),
    )


@pytest.fixture
def shift_with_yields(
    org, m_slaughter, slaughter_line, birds_batch, user, tushka_nom, grudka_nom, unit_kg
):
    shift = SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=birds_batch,
        doc_number="УБ-001", shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=1000,
        live_weight_kg_total=Decimal("2500.000"),
        foreman=user,
    )
    SlaughterYield.objects.create(
        shift=shift, nomenclature=tushka_nom, unit=unit_kg,
        quantity=Decimal("1500"), share_percent=Decimal("60.000"),
    )
    SlaughterYield.objects.create(
        shift=shift, nomenclature=grudka_nom, unit=unit_kg,
        quantity=Decimal("1000"), share_percent=Decimal("40.000"),
    )
    SlaughterQualityCheck.objects.create(
        shift=shift, vet_inspection_passed=True,
        inspector=user, inspected_at=datetime.now(timezone.utc),
    )
    return shift


# ─── Core flow ───────────────────────────────────────────────────────────


def test_post_shift_creates_output_batches(
    shift_with_yields, slaughter_fg_wh, feedlot_wh, birds_batch,
):
    result = post_slaughter_shift(
        shift_with_yields,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    assert len(result.output_batches) == 2
    # Проверка распределения cost: 10_000_000 * 60/100 = 6_000_000
    tushka = next(
        b for b in result.output_batches if b.nomenclature.sku == "ГП-Туш-01"
    )
    grudka = next(
        b for b in result.output_batches if b.nomenclature.sku == "ГП-Гр-01"
    )
    assert tushka.accumulated_cost_uzs == Decimal("6000000.00")
    assert grudka.accumulated_cost_uzs == Decimal("4000000.00")
    # Parent = source batch
    assert tushka.parent_batch_id == birds_batch.id


def test_post_shift_closes_source_batch(
    shift_with_yields, slaughter_fg_wh, feedlot_wh, birds_batch,
):
    post_slaughter_shift(
        shift_with_yields,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    birds_batch.refresh_from_db()
    assert birds_batch.state == Batch.State.COMPLETED
    assert birds_batch.current_quantity == Decimal("0")
    assert birds_batch.completed_at == date.today()


def test_post_shift_creates_both_je(shift_with_yields, slaughter_fg_wh, feedlot_wh):
    result = post_slaughter_shift(
        shift_with_yields,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    je_writeoff = result.journal_entries[0]
    je_finished = result.journal_entries[1]
    # #1: Dr 20.04 / Cr 10.02
    assert je_writeoff.debit_subaccount.code == "20.04"
    assert je_writeoff.credit_subaccount.code == "10.02"
    assert je_writeoff.amount_uzs == Decimal("10000000.00")
    # #2: Dr 43.01 / Cr 20.04
    assert je_finished.debit_subaccount.code == "43.01"
    assert je_finished.credit_subaccount.code == "20.04"
    assert je_finished.amount_uzs == Decimal("10000000.00")


def test_post_shift_marks_status_posted(shift_with_yields, slaughter_fg_wh, feedlot_wh):
    post_slaughter_shift(
        shift_with_yields,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    shift_with_yields.refresh_from_db()
    assert shift_with_yields.status == SlaughterShift.Status.POSTED
    assert shift_with_yields.end_time is not None


# ─── Guards ──────────────────────────────────────────────────────────────


def test_post_shift_already_posted_raises(
    shift_with_yields, slaughter_fg_wh, feedlot_wh,
):
    post_slaughter_shift(
        shift_with_yields,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift_with_yields,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


def test_post_shift_without_yields_raises(
    org, m_slaughter, slaughter_line, birds_batch, user, slaughter_fg_wh, feedlot_wh,
):
    shift = SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=birds_batch,
        doc_number="УБ-NOYIELDS", shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=100,
        live_weight_kg_total=Decimal("250.000"),
        foreman=user,
    )
    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


def test_post_shift_withdrawal_period_blocks(
    shift_with_yields, slaughter_fg_wh, feedlot_wh, birds_batch,
):
    # Устанавливаем активную каренцию — clean() SlaughterShift должен не пройти
    birds_batch.withdrawal_period_ends = date.today() + timedelta(days=3)
    birds_batch.save()
    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift_with_yields,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )
