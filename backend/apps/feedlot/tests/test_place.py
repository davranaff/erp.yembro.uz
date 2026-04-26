"""
Тесты place_feedlot_batch.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch
from apps.feedlot.services.place_batch import place_feedlot_batch
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
def m_incubation():
    return Module.objects.get(code="incubation")


@pytest.fixture
def user():
    return User.objects.create(email="f@y.local", full_name="F")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "гол"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(organization=org, name="Птица живая")[0]


@pytest.fixture
def nom(org, cat, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Бр-01", name="Цыпленок",
        category=cat, unit=unit_pcs,
    )


@pytest.fixture
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-1",
        name="Птичник", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def incubator(org, m_incubation):
    return ProductionBlock.objects.create(
        organization=org, module=m_incubation, code="ШК-1",
        name="Инкубатор", kind=ProductionBlock.Kind.INCUBATION,
    )


@pytest.fixture
def batch_in_feedlot(org, m_feedlot, house, nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-ЦБ-01",
        nomenclature=nom, unit=unit_pcs,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date(2026, 4, 1),
    )


def test_place_creates_feedlot_batch(batch_in_feedlot, house, user):
    result = place_feedlot_batch(
        batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
        technologist=user,
    )
    assert result.feedlot_batch.status == FeedlotBatch.Status.PLACED
    assert result.feedlot_batch.initial_heads == 10000
    assert result.feedlot_batch.current_heads == 10000
    assert result.feedlot_batch.batch_id == batch_in_feedlot.id
    assert result.feedlot_batch.doc_number.startswith("ФЛ-")


def test_place_explicit_heads(batch_in_feedlot, house, user):
    result = place_feedlot_batch(
        batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
        technologist=user, initial_heads=8000,
    )
    assert result.feedlot_batch.initial_heads == 8000


def test_place_exceeds_available_raises(batch_in_feedlot, house, user):
    with pytest.raises(ValidationError):
        place_feedlot_batch(
            batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
            technologist=user, initial_heads=20000,
        )


def test_place_zero_heads_raises(batch_in_feedlot, house, user):
    with pytest.raises(ValidationError):
        place_feedlot_batch(
            batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
            technologist=user, initial_heads=0,
        )


def test_place_wrong_module_raises(
    org, m_incubation, incubator, nom, unit_pcs, user
):
    batch_in_inc = Batch.objects.create(
        organization=org, doc_number="П-Я-99",
        nomenclature=nom, unit=unit_pcs,
        origin_module=m_incubation, current_module=m_incubation,
        current_block=incubator,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("100000"),
        started_at=date(2026, 4, 1),
    )
    with pytest.raises(ValidationError):
        place_feedlot_batch(
            batch_in_inc, house_block=incubator, placed_date=date(2026, 4, 1),
            technologist=user,
        )


def test_place_wrong_block_kind_raises(batch_in_feedlot, incubator, user):
    with pytest.raises(ValidationError):
        place_feedlot_batch(
            batch_in_feedlot, house_block=incubator,
            placed_date=date(2026, 4, 1), technologist=user,
        )


def test_place_duplicate_raises(batch_in_feedlot, house, user):
    place_feedlot_batch(
        batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
        technologist=user,
    )
    with pytest.raises(ValidationError):
        place_feedlot_batch(
            batch_in_feedlot, house_block=house, placed_date=date(2026, 4, 1),
            technologist=user,
        )
