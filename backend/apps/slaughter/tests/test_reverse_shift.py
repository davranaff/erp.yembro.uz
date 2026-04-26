"""
Тесты reverse_slaughter_shift — сторно проведённой смены убоя.
Переиспользуем сетап из test_post_shift через import фикстур.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.accounting.models import JournalEntry
from apps.batches.models import Batch
from apps.slaughter.models import SlaughterShift
from apps.slaughter.services.post_shift import post_slaughter_shift
from apps.slaughter.services.reverse_shift import (
    SlaughterReverseError,
    reverse_slaughter_shift,
)
from apps.warehouses.models import StockMovement

# Импортируем фикстуры из существующего теста — pytest найдёт их
# через conftest/recursive discovery, поэтому для надёжности
# делаем импорт явным.
from apps.slaughter.tests.test_post_shift import (  # noqa: F401
    org, m_feedlot, m_slaughter, user, unit_kg, unit_pcs,
    cat_live, cat_fg, chick_nom, tushka_nom, grudka_nom,
    feedlot_house, slaughter_line, feedlot_wh, slaughter_fg_wh,
    birds_batch, shift_with_yields,
)


pytestmark = pytest.mark.django_db


@pytest.fixture
def posted_shift(shift_with_yields, slaughter_fg_wh, feedlot_wh):
    post_slaughter_shift(
        shift_with_yields,
        source_warehouse=feedlot_wh,
        output_warehouse=slaughter_fg_wh,
    )
    shift_with_yields.refresh_from_db()
    return shift_with_yields


# ─── Core flow ───────────────────────────────────────────────────────────


def test_reverse_sets_cancelled(posted_shift):
    result = reverse_slaughter_shift(posted_shift, reason="ошибка")
    assert result.shift.status == SlaughterShift.Status.CANCELLED


def test_reverse_returns_source_batch(posted_shift, birds_batch):
    reverse_slaughter_shift(posted_shift)
    birds_batch.refresh_from_db()
    assert birds_batch.state == Batch.State.ACTIVE
    assert birds_batch.current_quantity == birds_batch.initial_quantity
    assert birds_batch.completed_at is None


def test_reverse_cancels_output_batches(posted_shift):
    reverse_slaughter_shift(posted_shift)
    outputs = Batch.objects.filter(parent_batch=posted_shift.source_batch)
    assert outputs.exists()
    for ob in outputs:
        assert ob.state == Batch.State.REJECTED
        assert ob.current_quantity == Decimal("0")


def test_reverse_creates_swapped_journals(posted_shift):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(SlaughterShift)

    orig_count = JournalEntry.objects.filter(
        source_content_type=ct, source_object_id=posted_shift.id,
    ).count()
    result = reverse_slaughter_shift(posted_shift)
    # orig + reverse (столько же сколько оригинальных)
    total = JournalEntry.objects.filter(
        source_content_type=ct, source_object_id=posted_shift.id,
    ).count()
    assert total == orig_count * 2
    assert len(result.reverse_journals) == orig_count


def test_reverse_creates_reverse_movements(posted_shift):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(SlaughterShift)

    orig_movements = StockMovement.objects.filter(
        source_content_type=ct, source_object_id=posted_shift.id,
    )
    orig_count = orig_movements.count()
    reverse_slaughter_shift(posted_shift)
    total = StockMovement.objects.filter(
        source_content_type=ct, source_object_id=posted_shift.id,
    ).count()
    assert total == orig_count * 2


# ─── Guards ──────────────────────────────────────────────────────────────


def test_reverse_active_shift_raises(shift_with_yields):
    with pytest.raises(ValidationError):
        reverse_slaughter_shift(shift_with_yields)


def test_reverse_twice_raises(posted_shift):
    reverse_slaughter_shift(posted_shift)
    with pytest.raises(ValidationError):
        reverse_slaughter_shift(posted_shift)


def test_reverse_after_output_movement_raises(posted_shift):
    """Если ГП уже отгрузили со склада — сторно невозможно."""
    output_batch = Batch.objects.filter(
        parent_batch=posted_shift.source_batch
    ).first()
    assert output_batch is not None
    output_batch.current_quantity = output_batch.initial_quantity - Decimal("1")
    output_batch.save(update_fields=["current_quantity"])
    with pytest.raises(ValidationError):
        reverse_slaughter_shift(posted_shift)
