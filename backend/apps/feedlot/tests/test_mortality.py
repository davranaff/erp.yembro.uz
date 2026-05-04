"""
Тесты apply_mortality — учёт падежа на feedlot-партии.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch, FeedlotMortality
from apps.feedlot.services.mortality import (
    MortalityError,
    apply_mortality,
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
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def user():
    return User.objects.create(email="f@y.local", full_name="F")


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
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-1",
        name="Птичник-1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def chick_batch(org, m_feedlot, house, chick_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-ЦБ-01",
        nomenclature=chick_nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date(2026, 4, 1),
    )


@pytest.fixture
def feedlot_batch(org, m_feedlot, house, chick_batch, user):
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=house, batch=chick_batch,
        doc_number="ФЛ-001",
        placed_date=date(2026, 4, 1),
        initial_heads=10000, current_heads=10000,
        status=FeedlotBatch.Status.GROWING,
        technologist=user,
    )


# ─── Core flow ───────────────────────────────────────────────────────────


def test_mortality_decrements_feedlot_and_batch(feedlot_batch, chick_batch):
    result = apply_mortality(
        feedlot_batch, date=date(2026, 4, 10),
        day_of_age=10, dead_count=50,
    )
    feedlot_batch.refresh_from_db()
    chick_batch.refresh_from_db()
    assert feedlot_batch.current_heads == 9950
    assert chick_batch.current_quantity == Decimal("9950")
    assert result.record.dead_count == 50
    assert result.record.day_of_age == 10


def test_mortality_creates_record_with_fields(feedlot_batch):
    result = apply_mortality(
        feedlot_batch, date=date(2026, 4, 10),
        day_of_age=10, dead_count=25,
        cause="натуральная", notes="пик жары",
    )
    rec = result.record
    assert rec.feedlot_batch_id == feedlot_batch.id
    assert rec.cause == "натуральная"
    assert rec.notes == "пик жары"
    assert isinstance(rec, FeedlotMortality)


def test_mortality_multiple_events_accumulate(feedlot_batch, chick_batch):
    apply_mortality(
        feedlot_batch, date=date(2026, 4, 10), day_of_age=10, dead_count=30,
    )
    apply_mortality(
        feedlot_batch, date=date(2026, 4, 11), day_of_age=11, dead_count=20,
    )
    feedlot_batch.refresh_from_db()
    chick_batch.refresh_from_db()
    assert feedlot_batch.current_heads == 9950
    assert chick_batch.current_quantity == Decimal("9950")


# ─── Guards ──────────────────────────────────────────────────────────────


def test_mortality_zero_raises(feedlot_batch):
    with pytest.raises(ValidationError):
        apply_mortality(
            feedlot_batch, date=date(2026, 4, 10), day_of_age=10, dead_count=0,
        )


def test_mortality_negative_raises(feedlot_batch):
    with pytest.raises(ValidationError):
        apply_mortality(
            feedlot_batch, date=date(2026, 4, 10), day_of_age=10, dead_count=-1,
        )


def test_mortality_exceeds_current_heads_raises(feedlot_batch):
    with pytest.raises(ValidationError):
        apply_mortality(
            feedlot_batch, date=date(2026, 4, 10), day_of_age=10,
            dead_count=15000,
        )


def test_mortality_exactly_current_heads_ok(feedlot_batch, chick_batch):
    """Граничный случай: падёж = ровно current_heads → 0 остаток."""
    apply_mortality(
        feedlot_batch, date=date(2026, 4, 10), day_of_age=10,
        dead_count=10000,
    )
    feedlot_batch.refresh_from_db()
    chick_batch.refresh_from_db()
    assert feedlot_batch.current_heads == 0
    assert chick_batch.current_quantity == Decimal("0")
