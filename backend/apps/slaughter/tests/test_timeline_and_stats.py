"""Тесты get_shift_timeline + get_shift_kpi."""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.batches.models import Batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import (
    SlaughterLabTest,
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)
from apps.slaughter.services.stats import get_shift_kpi
from apps.slaughter.services.timeline import get_shift_timeline
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


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
    return User.objects.create(email="t@y.local", full_name="T")


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
def carcass_nom(org, unit_kg):
    cat = Category.objects.get_or_create(organization=org, name="ГП")[0]
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku="CARCASS-WHOLE",
        defaults={"name": "Тушка целая", "category": cat, "unit": unit_kg},
    )
    return item


@pytest.fixture
def offal_nom(org, unit_kg):
    cat = Category.objects.get_or_create(organization=org, name="ГП")[0]
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku="OFFAL",
        defaults={"name": "Субпродукты", "category": cat, "unit": unit_kg},
    )
    return item


@pytest.fixture
def chick_nom(org, unit_pcs):
    cat = Category.objects.get_or_create(organization=org, name="ЖП")[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-T-01", name="Цыпленок",
        category=cat, unit=unit_pcs,
    )


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ТЛН-1",
        name="ТЛН-1", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def shift(org, m_slaughter, m_feedlot, slaughter_line, chick_nom, unit_pcs, user):
    batch = Batch.objects.create(
        organization=org, doc_number="ГТ-BATCH-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_slaughter,
        current_block=slaughter_line,
        current_quantity=Decimal("100"),
        initial_quantity=Decimal("100"),
        accumulated_cost_uzs=Decimal("1000000"),
        started_at=date.today(),
    )
    return SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=batch,
        doc_number="ТУБ-001", shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=100,
        live_weight_kg_total=Decimal("250"),
        foreman=user,
    )


# ── Stats ────────────────────────────────────────────────────────────────


def test_kpi_carcass_yield_pct(shift, carcass_nom, offal_nom, unit_kg, user):
    SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("175"),  # 175 / 250 = 70%
    )
    SlaughterYield.objects.create(
        shift=shift, nomenclature=offal_nom, unit=unit_kg,
        quantity=Decimal("50"),
    )
    SlaughterQualityCheck.objects.create(
        shift=shift, vet_inspection_passed=True,
        carcass_defect_percent=Decimal("1.50"),
        inspector=user, inspected_at=datetime.now(timezone.utc),
    )

    kpi = get_shift_kpi(shift)
    assert kpi.total_output_kg == Decimal("225")
    assert kpi.carcass_kg == Decimal("175")
    assert kpi.carcass_yield_pct == Decimal("70.00")
    assert kpi.yield_per_head_kg == Decimal("2.250")
    assert kpi.defect_rate == Decimal("1.50")
    assert kpi.quality_checked is True
    assert kpi.yields_count == 2
    # Σ выходов / отходы
    assert kpi.total_output_pct == Decimal("90.00")  # 225/250
    assert kpi.waste_kg == Decimal("25.000")
    assert kpi.waste_pct == Decimal("10.00")


def test_kpi_breakdown_includes_yields(shift, carcass_nom, offal_nom, unit_kg):
    """breakdown содержит строку на каждый kg-выход с yield_pct и нормой."""
    SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("180"),  # 180/250 = 72% — точно норма
    )
    SlaughterYield.objects.create(
        shift=shift, nomenclature=offal_nom, unit=unit_kg,
        quantity=Decimal("20"),  # 20/250 = 8% — точно норма
    )

    kpi = get_shift_kpi(shift)
    by_sku = {row.sku: row for row in kpi.breakdown}
    assert "CARCASS-WHOLE" in by_sku
    assert "OFFAL" in by_sku

    carcass_row = by_sku["CARCASS-WHOLE"]
    assert carcass_row.yield_pct == Decimal("72.00")
    assert carcass_row.norm_pct == Decimal("72.00")
    assert carcass_row.deviation_pct == Decimal("0.00")
    assert carcass_row.is_within_tolerance is True

    offal_row = by_sku["OFFAL"]
    assert offal_row.yield_pct == Decimal("8.00")
    assert offal_row.norm_pct == Decimal("8.00")
    assert offal_row.is_within_tolerance is True


def test_kpi_breakdown_flags_out_of_tolerance(shift, carcass_nom, unit_kg):
    """Отклонение >2% должно ставить is_within_tolerance=False."""
    SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("150"),  # 150/250 = 60% (норма 72% → отклонение -12%)
    )
    kpi = get_shift_kpi(shift)
    row = next(r for r in kpi.breakdown if r.sku == "CARCASS-WHOLE")
    assert row.yield_pct == Decimal("60.00")
    assert row.norm_pct == Decimal("72.00")
    assert row.deviation_pct == Decimal("-12.00")
    assert row.is_within_tolerance is False


def test_kpi_lab_counts(shift, user):
    SlaughterLabTest.objects.create(
        shift=shift, indicator="КМАФАнМ", normal_range="<1e5", actual_value="2e4",
        status=SlaughterLabTest.Status.PASSED, operator=user,
    )
    SlaughterLabTest.objects.create(
        shift=shift, indicator="Сальмонелла", normal_range="нет", actual_value="нет",
        status=SlaughterLabTest.Status.PENDING, operator=user,
    )
    SlaughterLabTest.objects.create(
        shift=shift, indicator="Листерия", normal_range="нет", actual_value="есть",
        status=SlaughterLabTest.Status.FAILED, operator=user,
    )
    kpi = get_shift_kpi(shift)
    assert kpi.lab_passed_count == 1
    assert kpi.lab_pending_count == 1
    assert kpi.lab_failed_count == 1


# ── Timeline ─────────────────────────────────────────────────────────────


def test_timeline_includes_created_event(shift):
    events = get_shift_timeline(shift)
    types = [e["type"] for e in events]
    assert "created" in types


def test_timeline_includes_quality_lab_yield(shift, carcass_nom, unit_kg, user):
    SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("150"),
    )
    SlaughterQualityCheck.objects.create(
        shift=shift, vet_inspection_passed=True,
        inspector=user, inspected_at=datetime.now(timezone.utc),
    )
    SlaughterLabTest.objects.create(
        shift=shift, indicator="КМАФАнМ", normal_range="<1e5", actual_value="2e4",
        status=SlaughterLabTest.Status.PASSED, operator=user,
    )
    events = get_shift_timeline(shift)
    types = {e["type"] for e in events}
    assert {"created", "quality", "lab", "yield"}.issubset(types)


def test_timeline_includes_posted_when_status_posted(shift):
    shift.status = SlaughterShift.Status.POSTED
    shift.save()
    events = get_shift_timeline(shift)
    types = [e["type"] for e in events]
    assert "posted" in types
