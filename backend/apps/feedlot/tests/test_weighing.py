"""
Тесты record_weighing — контрольные взвешивания + status transitions.
"""
from datetime import date
from decimal import Decimal

import pytest

from apps.batches.models import Batch
from apps.feedlot.models import DailyWeighing, FeedlotBatch
from apps.feedlot.services.weighing import (
    WeighingError,
    record_weighing,
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
    return User.objects.create(email="w@y.local", full_name="W")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="голW", defaults={"name": "Голов"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(
        organization=org, name="Птица живая (W)"
    )[0]


@pytest.fixture
def nom(org, cat, unit_pcs):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЦБ-W", name="Бройлер W",
        category=cat, unit=unit_pcs,
    )


@pytest.fixture
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-W-1",
        name="Птичник W1", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def chick_batch(org, m_feedlot, house, nom, unit_pcs):
    return Batch.objects.create(
        organization=org, doc_number="П-W-ЦБ-01",
        nomenclature=nom, unit=unit_pcs,
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
        doc_number="ФЛ-W-001", placed_date=date(2026, 4, 1),
        target_weight_kg=Decimal("2.500"),
        initial_heads=10000, current_heads=10000,
        status=FeedlotBatch.Status.PLACED,
        technologist=user,
    )


def test_first_weighing_transitions_placed_to_growing(
    feedlot_batch, user,
):
    """Первое взвешивание переводит status PLACED → GROWING."""
    assert feedlot_batch.status == FeedlotBatch.Status.PLACED

    result = record_weighing(
        feedlot_batch,
        date=date(2026, 4, 2),
        day_of_age=1,
        sample_size=50,
        avg_weight_kg=Decimal("0.050"),
        user=user,
    )

    assert result.status_changed is True
    feedlot_batch.refresh_from_db()
    assert feedlot_batch.status == FeedlotBatch.Status.GROWING
    assert result.weighing.gain_kg is None  # первое — нет prev


def test_weighing_at_target_transitions_to_ready_slaughter(
    feedlot_batch, user,
):
    """Если avg_weight ≥ target → READY_SLAUGHTER."""
    # Сразу впишем взвешивание с avg = target
    result = record_weighing(
        feedlot_batch,
        date=date(2026, 5, 14),
        day_of_age=42,
        sample_size=50,
        avg_weight_kg=Decimal("2.600"),  # > target 2.5
        user=user,
    )

    assert result.status_changed is True
    feedlot_batch.refresh_from_db()
    assert feedlot_batch.status == FeedlotBatch.Status.READY_SLAUGHTER


def test_weighing_computes_gain_from_previous(
    feedlot_batch, user,
):
    """gain_kg = avg − previous_avg."""
    record_weighing(
        feedlot_batch,
        date=date(2026, 4, 2), day_of_age=1,
        sample_size=50, avg_weight_kg=Decimal("0.050"),
        user=user,
    )
    result2 = record_weighing(
        feedlot_batch,
        date=date(2026, 4, 9), day_of_age=8,
        sample_size=50, avg_weight_kg=Decimal("0.250"),
        user=user,
    )
    assert result2.weighing.gain_kg == Decimal("0.200")


def test_weighing_duplicate_day_raises(
    feedlot_batch, user,
):
    """Уникальность (feedlot_batch, day_of_age) — повтор → ошибка."""
    record_weighing(
        feedlot_batch,
        date=date(2026, 4, 2), day_of_age=1,
        sample_size=50, avg_weight_kg=Decimal("0.050"),
        user=user,
    )
    with pytest.raises(WeighingError) as exc:
        record_weighing(
            feedlot_batch,
            date=date(2026, 4, 3), day_of_age=1,  # тот же день
            sample_size=50, avg_weight_kg=Decimal("0.060"),
            user=user,
        )
    assert "уже записано" in str(exc.value.message_dict)


def test_weighing_invalid_sample_size_raises(feedlot_batch, user):
    with pytest.raises(WeighingError):
        record_weighing(
            feedlot_batch,
            date=date(2026, 4, 2), day_of_age=1,
            sample_size=0, avg_weight_kg=Decimal("0.050"),
            user=user,
        )


def test_weighing_shipped_feedlot_raises(feedlot_batch, user):
    feedlot_batch.status = FeedlotBatch.Status.SHIPPED
    feedlot_batch.save(update_fields=["status"])
    with pytest.raises(WeighingError):
        record_weighing(
            feedlot_batch,
            date=date(2026, 4, 2), day_of_age=1,
            sample_size=50, avg_weight_kg=Decimal("0.050"),
            user=user,
        )
