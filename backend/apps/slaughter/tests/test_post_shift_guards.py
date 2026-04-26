"""
Тесты гардов post_slaughter_shift:
  - source_batch.current_module == slaughter
  - vet_inspection_passed == True
  - Σ(yields_kg) ≈ live_weight ±10%
  - source_warehouse обязателен
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import (
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)
from apps.slaughter.services.post_shift import post_slaughter_shift
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
    return User.objects.create(email="g@y.local", full_name="G")


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
        organization=org, sku="ЖП-G-01", name="Цыпленок",
        category=cat_live, unit=unit_pcs,
    )


@pytest.fixture
def carcass_nom(org, cat_fg, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="ГП-Т-01", name="Тушка",
        category=cat_fg, unit=unit_kg,
    )


@pytest.fixture
def feedlot_house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ГА-1",
        name="ГА-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ГЛН-1",
        name="ГЛН-1", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def feedlot_wh(org, m_feedlot):
    return Warehouse.objects.create(
        organization=org, module=m_feedlot, code="ГСК-Ф", name="GSF",
    )


@pytest.fixture
def slaughter_fg_wh(org, m_slaughter):
    return Warehouse.objects.create(
        organization=org, module=m_slaughter, code="ГСК-ГП", name="GSG",
    )


def _make_batch(org, m_feedlot, m_slaughter, current_module, current_block,
                chick_nom, unit_pcs, doc):
    return Batch.objects.create(
        organization=org, doc_number=doc,
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=current_module,
        current_block=current_block,
        current_quantity=Decimal("100"),
        initial_quantity=Decimal("100"),
        accumulated_cost_uzs=Decimal("1000000.00"),
        started_at=date.today(),
    )


def _make_shift(org, m_slaughter, slaughter_line, batch, user, doc, weight=Decimal("250")):
    return SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=batch,
        doc_number=doc, shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=100,
        live_weight_kg_total=weight,
        foreman=user,
    )


def _add_yield(shift, nom, unit_kg, qty):
    return SlaughterYield.objects.create(
        shift=shift, nomenclature=nom, unit=unit_kg,
        quantity=qty, share_percent=Decimal("100.000"),
    )


def _add_qc(shift, user, passed=True):
    return SlaughterQualityCheck.objects.create(
        shift=shift, vet_inspection_passed=passed,
        inspector=user, inspected_at=datetime.now(timezone.utc),
    )


# ── Guard 1: current_module ──────────────────────────────────────────────


def test_post_blocked_when_batch_not_in_slaughter_module(
    org, m_feedlot, m_slaughter, slaughter_line, feedlot_house,
    chick_nom, unit_pcs, unit_kg, carcass_nom, user,
    slaughter_fg_wh, feedlot_wh,
):
    """Партия в модуле feedlot — нельзя провести смену убоя."""
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_feedlot,  # !!! не slaughter
        current_block=feedlot_house,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-MOD-01",
    )
    shift = _make_shift(org, m_slaughter, slaughter_line, batch, user, "ГУБ-MOD")
    _add_yield(shift, carcass_nom, unit_kg, Decimal("250"))
    _add_qc(shift, user, passed=True)

    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


# ── Guard 2: vet_inspection_passed ──────────────────────────────────────


def test_post_blocked_without_quality_check(
    org, m_feedlot, m_slaughter, slaughter_line, chick_nom, unit_pcs,
    unit_kg, carcass_nom, user, slaughter_fg_wh, feedlot_wh,
):
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_slaughter, current_block=slaughter_line,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-VET-01",
    )
    shift = _make_shift(org, m_slaughter, slaughter_line, batch, user, "ГУБ-VET-01")
    _add_yield(shift, carcass_nom, unit_kg, Decimal("250"))
    # QC не создан

    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


def test_post_blocked_when_vet_inspection_failed(
    org, m_feedlot, m_slaughter, slaughter_line, chick_nom, unit_pcs,
    unit_kg, carcass_nom, user, slaughter_fg_wh, feedlot_wh,
):
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_slaughter, current_block=slaughter_line,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-VET-02",
    )
    shift = _make_shift(org, m_slaughter, slaughter_line, batch, user, "ГУБ-VET-02")
    _add_yield(shift, carcass_nom, unit_kg, Decimal("250"))
    _add_qc(shift, user, passed=False)  # !!! не пройдена

    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


# ── Guard 3: yields balance ─────────────────────────────────────────────


def test_post_blocked_when_yields_deviate_too_much(
    org, m_feedlot, m_slaughter, slaughter_line, chick_nom, unit_pcs,
    unit_kg, carcass_nom, user, slaughter_fg_wh, feedlot_wh,
):
    """Живой вес 250 кг, выход 100 кг — отклонение 60% → отказ."""
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_slaughter, current_block=slaughter_line,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-W-01",
    )
    shift = _make_shift(
        org, m_slaughter, slaughter_line, batch, user, "ГУБ-W-01",
        weight=Decimal("250"),
    )
    _add_yield(shift, carcass_nom, unit_kg, Decimal("100"))  # 60% отклонение
    _add_qc(shift, user, passed=True)

    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=feedlot_wh,
        )


def test_post_ok_when_yields_within_tolerance(
    org, m_feedlot, m_slaughter, slaughter_line, chick_nom, unit_pcs,
    unit_kg, carcass_nom, user, slaughter_fg_wh, feedlot_wh,
):
    """Живой 250 кг, выход 235 кг — отклонение 6% → проходит."""
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_slaughter, current_block=slaughter_line,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-W-OK",
    )
    shift = _make_shift(
        org, m_slaughter, slaughter_line, batch, user, "ГУБ-W-OK",
        weight=Decimal("250"),
    )
    _add_yield(shift, carcass_nom, unit_kg, Decimal("235"))
    _add_qc(shift, user, passed=True)

    result = post_slaughter_shift(
        shift,
        output_warehouse=slaughter_fg_wh,
        source_warehouse=feedlot_wh,
    )
    assert result.shift.status == SlaughterShift.Status.POSTED


# ── Guard 4: source_warehouse required ──────────────────────────────────


def test_post_blocked_without_source_warehouse(
    org, m_feedlot, m_slaughter, slaughter_line, chick_nom, unit_pcs,
    unit_kg, carcass_nom, user, slaughter_fg_wh,
):
    batch = _make_batch(
        org, m_feedlot, m_slaughter,
        current_module=m_slaughter, current_block=slaughter_line,
        chick_nom=chick_nom, unit_pcs=unit_pcs, doc="ГБ-WH-01",
    )
    shift = _make_shift(org, m_slaughter, slaughter_line, batch, user, "ГУБ-WH-01")
    _add_yield(shift, carcass_nom, unit_kg, Decimal("250"))
    _add_qc(shift, user, passed=True)

    with pytest.raises(ValidationError):
        post_slaughter_shift(
            shift,
            output_warehouse=slaughter_fg_wh,
            source_warehouse=None,
        )
