"""
Тесты close_batch.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.batches.models import Batch, BatchChainStep
from apps.batches.services.close_batch import close_batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def unit(org):
    return Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "гол"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(organization=org, name="Птица")[0]


@pytest.fixture
def nom(org, cat, unit):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-01", name="Цыпленок",
        category=cat, unit=unit,
    )


@pytest.fixture
def block(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-1",
        name="П1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def empty_batch(org, m_feedlot, block, nom, unit):
    b = Batch.objects.create(
        organization=org, doc_number="П-01",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=block,
        current_quantity=Decimal("0"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("500000"),
        started_at=date.today() - timedelta(days=40),
    )
    BatchChainStep.objects.create(
        batch=b, sequence=1, module=m_feedlot, block=block,
        entered_at=timezone.now(),
        quantity_in=Decimal("1000"),
    )
    return b


@pytest.fixture
def non_empty_batch(org, m_feedlot, block, nom, unit):
    return Batch.objects.create(
        organization=org, doc_number="П-02",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=block,
        current_quantity=Decimal("500"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("500000"),
        started_at=date.today() - timedelta(days=40),
    )


def test_close_empty_batch(empty_batch):
    result = close_batch(empty_batch, reason="end of cycle")
    empty_batch.refresh_from_db()
    assert empty_batch.state == Batch.State.COMPLETED
    assert empty_batch.completed_at is not None
    assert result.closed_chain_step is not None
    assert result.closed_chain_step.exited_at is not None


def test_close_non_empty_without_force_raises(non_empty_batch):
    with pytest.raises(ValidationError):
        close_batch(non_empty_batch)


def test_close_non_empty_with_force(non_empty_batch):
    close_batch(non_empty_batch, force=True, reason="принудительное списание")
    non_empty_batch.refresh_from_db()
    assert non_empty_batch.state == Batch.State.COMPLETED
    assert non_empty_batch.current_quantity == Decimal("0")


def test_close_already_completed_raises(empty_batch):
    close_batch(empty_batch)
    with pytest.raises(ValidationError):
        close_batch(empty_batch)
