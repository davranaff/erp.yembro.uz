"""
Тесты crystallize_egg_batch — сборка суточных яйцесборов в Egg Batch.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch, BatchChainStep
from apps.matochnik.models import BreedingHerd, DailyEggProduction
from apps.matochnik.services.crystallize import (
    EggCrystallizeError,
    crystallize_egg_batch,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def user():
    return User.objects.create(email="m@y.local", full_name="M")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штуки"}
    )[0]


@pytest.fixture
def cat_egg(org):
    return Category.objects.get_or_create(organization=org, name="Яйцо")[0]


@pytest.fixture
def egg_nom(org, cat_egg, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="СЫ-Я-ИНК-01",
        name="Яйцо инкубационное", category=cat_egg, unit=unit_pcs,
    )


@pytest.fixture
def herd_block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik, code="КС-М-1",
        name="Корпус маточника", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def herd(org, m_matochnik, herd_block, user):
    return BreedingHerd.objects.create(
        organization=org, module=m_matochnik, block=herd_block,
        doc_number="СТ-001",
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date(2026, 1, 1),
        initial_heads=10000, current_heads=9800,
        age_weeks_at_placement=25,
        status=BreedingHerd.Status.PRODUCING,
        technologist=user,
    )


@pytest.fixture
def records(herd):
    base = date(2026, 4, 20)
    recs = []
    for i in range(5):
        recs.append(
            DailyEggProduction.objects.create(
                herd=herd, date=base + timedelta(days=i),
                eggs_collected=1000, unfit_eggs=50,
            )
        )
    return recs


# ─── Core flow ───────────────────────────────────────────────────────────


def test_crystallize_creates_egg_batch(herd, egg_nom, records):
    result = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
    )
    # 5 дней * (1000 - 50) = 4750
    assert result.total_eggs == 4750
    assert result.records_count == 5
    assert result.batch.current_quantity == Decimal("4750")
    assert result.batch.initial_quantity == Decimal("4750")
    assert result.batch.nomenclature_id == egg_nom.id
    assert result.batch.accumulated_cost_uzs == Decimal("0")


def test_crystallize_links_records_to_batch(herd, egg_nom, records):
    result = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
    )
    for r in records:
        r.refresh_from_db()
        assert r.outgoing_batch_id == result.batch.id


def test_crystallize_creates_chain_step(herd, egg_nom, records):
    result = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
    )
    step = result.chain_step
    assert step.sequence == 1
    assert step.batch_id == result.batch.id
    assert step.quantity_in == Decimal("4750")
    assert step.module_id == herd.module_id


def test_crystallize_custom_doc_number(herd, egg_nom, records):
    result = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
        doc_number="П-Я-СПЕЦ-01",
    )
    assert result.batch.doc_number == "П-Я-СПЕЦ-01"


def test_crystallize_skips_already_linked(herd, egg_nom, records):
    """Записи с outgoing_batch ≠ NULL не должны пересобираться."""
    # Первый сбор — дни 20..22
    first = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 22),
    )
    assert first.total_eggs == 3 * 950  # 2850

    # Второй сбор — пересекающийся диапазон 21..24 → только 23, 24
    second = crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 21), date_to=date(2026, 4, 24),
    )
    assert second.records_count == 2
    assert second.total_eggs == 2 * 950  # 1900


# ─── Guards ──────────────────────────────────────────────────────────────


def test_crystallize_no_records_raises(herd, egg_nom):
    with pytest.raises(ValidationError):
        crystallize_egg_batch(
            herd, egg_nomenclature=egg_nom,
            date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
        )


def test_crystallize_invalid_range_raises(herd, egg_nom, records):
    with pytest.raises(ValidationError):
        crystallize_egg_batch(
            herd, egg_nomenclature=egg_nom,
            date_from=date(2026, 4, 24), date_to=date(2026, 4, 20),
        )


def test_crystallize_all_records_already_linked_raises(herd, egg_nom, records):
    crystallize_egg_batch(
        herd, egg_nomenclature=egg_nom,
        date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
    )
    with pytest.raises(ValidationError):
        crystallize_egg_batch(
            herd, egg_nomenclature=egg_nom,
            date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
        )


def test_crystallize_all_unfit_raises(herd, egg_nom):
    """Если все яйца — брак, партию не создать."""
    DailyEggProduction.objects.create(
        herd=herd, date=date(2026, 4, 20),
        eggs_collected=500, unfit_eggs=500,
    )
    with pytest.raises(ValidationError):
        crystallize_egg_batch(
            herd, egg_nomenclature=egg_nom,
            date_from=date(2026, 4, 20), date_to=date(2026, 4, 20),
        )


def test_crystallize_cross_org_nomenclature_raises(herd, unit_pcs, cat_egg):
    from apps.currency.models import Currency

    uzs = Currency.objects.get(code="UZS")
    other_org = Organization.objects.create(
        code="OTHER", name="Other", accounting_currency=uzs,
    )
    other_cat = Category.objects.create(organization=other_org, name="Яйцо")
    other_unit = Unit.objects.create(organization=other_org, code="шт", name="шт")
    foreign_nom = NomenclatureItem.objects.create(
        organization=other_org, sku="X", name="Другая", category=other_cat, unit=other_unit,
    )
    with pytest.raises(ValidationError):
        crystallize_egg_batch(
            herd, egg_nomenclature=foreign_nom,
            date_from=date(2026, 4, 20), date_to=date(2026, 4, 24),
        )
