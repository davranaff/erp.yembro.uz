"""
Тесты depopulate_herd.
"""
from datetime import date

import pytest
from django.core.exceptions import ValidationError

from apps.matochnik.models import BreedingHerd, BreedingMortality
from apps.matochnik.services.depopulate_herd import depopulate_herd
from apps.modules.models import Module
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
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik, code="КС-1",
        name="Корпус", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def herd(org, m_matochnik, block, user):
    return BreedingHerd.objects.create(
        organization=org, module=m_matochnik, block=block,
        doc_number="СТ-001",
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date(2026, 1, 1),
        initial_heads=10000, current_heads=10000,
        age_weeks_at_placement=25,
        status=BreedingHerd.Status.PRODUCING,
        technologist=user,
    )


def test_reduce_heads(herd):
    result = depopulate_herd(herd, reduce_by=100, reason="плановое")
    herd.refresh_from_db()
    assert herd.current_heads == 9900
    assert herd.status == BreedingHerd.Status.PRODUCING


def test_full_depopulation_sets_status(herd):
    depopulate_herd(herd, reduce_by=10000, reason="полное снятие")
    herd.refresh_from_db()
    assert herd.current_heads == 0
    assert herd.status == BreedingHerd.Status.DEPOPULATED


def test_mark_as_mortality_creates_record(herd):
    result = depopulate_herd(
        herd, reduce_by=50, date=date(2026, 4, 20),
        reason="жара", mark_as_mortality=True,
    )
    assert result.mortality_record is not None
    assert result.mortality_record.dead_count == 50
    assert result.mortality_record.cause == "плановое снятие"


def test_zero_raises(herd):
    with pytest.raises(ValidationError):
        depopulate_herd(herd, reduce_by=0)


def test_negative_raises(herd):
    with pytest.raises(ValidationError):
        depopulate_herd(herd, reduce_by=-1)


def test_exceeds_current_raises(herd):
    with pytest.raises(ValidationError):
        depopulate_herd(herd, reduce_by=20000)


def test_already_depopulated_raises(herd):
    herd.status = BreedingHerd.Status.DEPOPULATED
    herd.current_heads = 0
    herd.save()
    with pytest.raises(ValidationError):
        depopulate_herd(herd, reduce_by=100)
