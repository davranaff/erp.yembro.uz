"""
Тесты сигнала post_save BreedingMortality → decrement current_heads.

Ключевые сценарии:
    1. Создание записи падежа уменьшает current_heads.
    2. Падёж до 0 переводит стадо в DEPOPULATED.
    3. Update существующей записи не декрементит (это делает depopulate-сервис).
    4. depopulate(mark_as_mortality=True) с create — не удваивает декремент.
    5. depopulate(mark_as_mortality=True) с update (merge) — декрементит.
"""
from datetime import date

import pytest

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
        organization=org, module=m_matochnik, code="КС-SIG",
        name="Корпус", kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def herd(org, m_matochnik, block, user):
    return BreedingHerd.objects.create(
        organization=org, module=m_matochnik, block=block,
        doc_number="СТ-SIG-01",
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date(2026, 1, 1),
        initial_heads=5000, current_heads=5000,
        age_weeks_at_placement=25,
        status=BreedingHerd.Status.PRODUCING,
        technologist=user,
    )


def test_create_mortality_decrements_heads(herd):
    BreedingMortality.objects.create(
        herd=herd, date=date(2026, 4, 20), dead_count=30,
        cause="жара",
    )
    herd.refresh_from_db()
    assert herd.current_heads == 4970
    assert herd.status == BreedingHerd.Status.PRODUCING


def test_mortality_to_zero_sets_depopulated(herd):
    BreedingMortality.objects.create(
        herd=herd, date=date(2026, 4, 20), dead_count=5000,
        cause="вспышка",
    )
    herd.refresh_from_db()
    assert herd.current_heads == 0
    assert herd.status == BreedingHerd.Status.DEPOPULATED


def test_mortality_overflow_does_not_break(herd):
    """Если dead_count > current_heads — current_heads=0, не уходит в минус."""
    # Текущий сигнал просто декрементит через F() — пусть падёт в 0
    BreedingMortality.objects.create(
        herd=herd, date=date(2026, 4, 20), dead_count=10000,
        cause="массовый",
    )
    herd.refresh_from_db()
    # current_heads — PositiveIntegerField, поэтому либо 0 либо сигнал пропустит.
    # Наш сигнал ставит 0 через проверку <=0.
    assert herd.current_heads == 0
    assert herd.status == BreedingHerd.Status.DEPOPULATED


def test_update_mortality_does_not_decrement(herd):
    """Изменение существующей записи падежа — сигнал не срабатывает."""
    record = BreedingMortality.objects.create(
        herd=herd, date=date(2026, 4, 20), dead_count=30,
    )
    herd.refresh_from_db()
    heads_after_create = herd.current_heads

    record.dead_count = 50
    record.save(update_fields=["dead_count", "updated_at"])

    herd.refresh_from_db()
    assert herd.current_heads == heads_after_create


def test_depopulate_with_mortality_does_not_double_decrement(herd):
    """depopulate(mark_as_mortality=True) при create — одинарный декремент."""
    result = depopulate_herd(
        herd, reduce_by=100, date=date(2026, 4, 20),
        mark_as_mortality=True, reason="санитарное",
    )
    herd.refresh_from_db()
    assert herd.current_heads == 4900
    assert result.mortality_record is not None
    assert result.mortality_record.dead_count == 100


def test_depopulate_merge_mortality_still_works(herd):
    """
    Если за дату уже есть запись падежа, второй depopulate(mark=True)
    делает merge (update существующей) и вручную декрементит current_heads.
    """
    # Первый вызов → create
    depopulate_herd(
        herd, reduce_by=100, date=date(2026, 4, 20),
        mark_as_mortality=True, reason="день 1",
    )
    herd.refresh_from_db()
    assert herd.current_heads == 4900

    # Второй вызов → update (merge)
    depopulate_herd(
        herd, reduce_by=50, date=date(2026, 4, 20),
        mark_as_mortality=True, reason="день 1 дополнение",
    )
    herd.refresh_from_db()
    assert herd.current_heads == 4850

    # В записи одна строка с суммой
    records = BreedingMortality.objects.filter(herd=herd, date=date(2026, 4, 20))
    assert records.count() == 1
    assert records.first().dead_count == 150
