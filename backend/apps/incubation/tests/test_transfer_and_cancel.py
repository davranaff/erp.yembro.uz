"""
Тесты transfer_to_hatcher и cancel_incubation_run.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch
from apps.incubation.models import IncubationRun
from apps.incubation.services.cancel import cancel_incubation_run
from apps.incubation.services.transfer_to_hatcher import transfer_to_hatcher
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
def m_incubation():
    return Module.objects.get(code="incubation")


@pytest.fixture
def user():
    return User.objects.create(email="i@y.local", full_name="I")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "шт"}
    )[0]


@pytest.fixture
def cat_egg(org):
    return Category.objects.get_or_create(organization=org, name="Яйцо")[0]


@pytest.fixture
def egg_nom(org, cat_egg, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="Я-ИНК-01", name="Яйцо",
        category=cat_egg, unit=unit_pcs,
    )


@pytest.fixture
def cabinet(org, m_incubation):
    return ProductionBlock.objects.create(
        organization=org, module=m_incubation, code="ШК-1",
        name="Инкубатор", kind=ProductionBlock.Kind.INCUBATION,
    )


@pytest.fixture
def hatcher(org, m_incubation):
    return ProductionBlock.objects.create(
        organization=org, module=m_incubation, code="ВВ-1",
        name="Выводной", kind=ProductionBlock.Kind.HATCHER,
    )


@pytest.fixture
def egg_batch(org, m_incubation, cabinet, egg_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-Я-01",
        nomenclature=egg_nom, unit=unit_pcs,
        origin_module=m_incubation, current_module=m_incubation,
        current_block=cabinet,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("1000000"),
        started_at=date.today() - timedelta(days=20),
    )


@pytest.fixture
def run(org, m_incubation, cabinet, egg_batch, user):
    return IncubationRun.objects.create(
        organization=org, module=m_incubation,
        doc_number="ИН-001",
        incubator_block=cabinet, batch=egg_batch,
        loaded_date=date.today() - timedelta(days=20),
        expected_hatch_date=date.today() + timedelta(days=1),
        eggs_loaded=1000,
        technologist=user,
    )


# ─── transfer_to_hatcher ─────────────────────────────────────────────────


def test_transfer_sets_hatching(run, hatcher):
    result = transfer_to_hatcher(run, hatcher_block=hatcher)
    assert result.run.status == IncubationRun.Status.HATCHING
    assert result.run.hatcher_block_id == hatcher.id


def test_transfer_from_wrong_status_raises(run, hatcher):
    run.status = IncubationRun.Status.TRANSFERRED
    run.save()
    with pytest.raises(ValidationError):
        transfer_to_hatcher(run, hatcher_block=hatcher)


def test_transfer_wrong_block_kind_raises(run, cabinet):
    with pytest.raises(ValidationError):
        transfer_to_hatcher(run, hatcher_block=cabinet)


# ─── cancel_incubation_run ───────────────────────────────────────────────


def test_cancel_closes_egg_batch(run, egg_batch):
    cancel_incubation_run(run, reason="incident")
    run.refresh_from_db()
    egg_batch.refresh_from_db()
    assert run.status == IncubationRun.Status.CANCELLED
    assert egg_batch.state == Batch.State.COMPLETED
    assert egg_batch.current_quantity == Decimal("0")


def test_cancel_after_transferred_raises(run):
    run.status = IncubationRun.Status.TRANSFERRED
    run.save()
    with pytest.raises(ValidationError):
        cancel_incubation_run(run, reason="late")


def test_cancel_from_hatching_ok(run, hatcher, egg_batch):
    transfer_to_hatcher(run, hatcher_block=hatcher)
    run.refresh_from_db()
    cancel_incubation_run(run, reason="провал вывода")
    run.refresh_from_db()
    assert run.status == IncubationRun.Status.CANCELLED
