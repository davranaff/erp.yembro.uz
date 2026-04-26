"""
Тесты hatch_incubation_run.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.batches.models import Batch, BatchChainStep
from apps.incubation.models import IncubationRun
from apps.incubation.services.hatch import (
    IncubationHatchError,
    hatch_incubation_run,
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
def cat_chick(org):
    return Category.objects.get_or_create(organization=org, name="Птица живая")[0]


@pytest.fixture
def egg_nom(org, cat_egg, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="СЫ-Инк-01", name="Яйцо",
        category=cat_egg, unit=unit_pcs,
    )


@pytest.fixture
def chick_nom(org, cat_chick, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Сут-01", name="Цыпленок",
        category=cat_chick, unit=unit_pcs,
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
        organization=org, module=m_incubation, code="ВЫВ-1",
        name="Выводной", kind=ProductionBlock.Kind.HATCHER,
    )


@pytest.fixture
def egg_batch(org, m_incubation, cabinet, egg_nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-EGG-01",
        nomenclature=egg_nom, unit=unit_pcs,
        origin_module=m_incubation, current_module=m_incubation,
        current_block=cabinet,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("5000000.00"),
        started_at=date.today() - timedelta(days=21),
    )


@pytest.fixture
def run(org, m_incubation, cabinet, hatcher, egg_batch, user):
    return IncubationRun.objects.create(
        organization=org, module=m_incubation,
        doc_number="ИН-001",
        incubator_block=cabinet,
        hatcher_block=hatcher,
        batch=egg_batch,
        loaded_date=date.today() - timedelta(days=21),
        expected_hatch_date=date.today(),
        eggs_loaded=1000,
        days_total=21,
        status=IncubationRun.Status.HATCHING,
        technologist=user,
    )


# ─── Core flow ───────────────────────────────────────────────────────────


def test_hatch_creates_chick_batch(run, chick_nom, egg_batch):
    result = hatch_incubation_run(
        run,
        chick_nomenclature=chick_nom,
        hatched_count=920,
        discarded_count=80,
        actual_hatch_date=date.today(),
    )
    assert result.chick_batch.nomenclature_id == chick_nom.id
    assert result.chick_batch.current_quantity == Decimal("920")
    assert result.chick_batch.parent_batch_id == egg_batch.id
    # Cost inheritance
    assert result.chick_batch.accumulated_cost_uzs == Decimal("5000000.00")


def test_hatch_closes_egg_batch(run, chick_nom, egg_batch):
    hatch_incubation_run(
        run,
        chick_nomenclature=chick_nom,
        hatched_count=920,
        actual_hatch_date=date.today(),
    )
    egg_batch.refresh_from_db()
    assert egg_batch.state == Batch.State.COMPLETED
    assert egg_batch.current_quantity == Decimal("0")
    assert egg_batch.completed_at == date.today()


def test_hatch_creates_chain_step(run, chick_nom):
    result = hatch_incubation_run(
        run,
        chick_nomenclature=chick_nom,
        hatched_count=920,
        actual_hatch_date=date.today(),
    )
    assert result.chain_step.sequence == 1
    assert result.chain_step.batch_id == result.chick_batch.id


def test_hatch_updates_run_status(run, chick_nom):
    hatch_incubation_run(
        run,
        chick_nomenclature=chick_nom,
        hatched_count=920,
        discarded_count=80,
        actual_hatch_date=date.today(),
    )
    run.refresh_from_db()
    assert run.status == IncubationRun.Status.TRANSFERRED
    assert run.hatched_count == 920
    assert run.discarded_count == 80


# ─── Guards ──────────────────────────────────────────────────────────────


def test_hatch_already_transferred_raises(run, chick_nom):
    run.status = IncubationRun.Status.TRANSFERRED
    run.save()
    with pytest.raises(ValidationError):
        hatch_incubation_run(
            run,
            chick_nomenclature=chick_nom,
            hatched_count=100,
            actual_hatch_date=date.today(),
        )


def test_hatch_too_many_raises(run, chick_nom):
    with pytest.raises(ValidationError):
        hatch_incubation_run(
            run,
            chick_nomenclature=chick_nom,
            hatched_count=9999,  # > eggs_loaded=1000
            actual_hatch_date=date.today(),
        )


def test_hatch_no_date_raises(run, chick_nom):
    # run.actual_hatch_date = None, и не передаём в сервис
    with pytest.raises(ValidationError):
        hatch_incubation_run(
            run,
            chick_nomenclature=chick_nom,
            hatched_count=100,
        )
