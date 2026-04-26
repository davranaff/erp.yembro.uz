"""
Тесты ImmutableStatusMixin и DeleteReasonMixin через ViewSet'ы.
Используем SlaughterShift (immutable=posted, cancelled) и SlaughterYield (delete reason).
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.batches.models import Batch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.slaughter.models import SlaughterShift, SlaughterYield
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_slaughter():
    return Module.objects.get(code="slaughter")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def user():
    return User.objects.create(email="lc@y.local", full_name="LC")


@pytest.fixture
def slaughter_line(org, m_slaughter):
    return ProductionBlock.objects.create(
        organization=org, module=m_slaughter, code="ЛН-LC",
        name="Линия LC", kind=ProductionBlock.Kind.SLAUGHTER_LINE,
    )


@pytest.fixture
def chick_nom(org):
    cat = Category.objects.get_or_create(organization=org, name="Жив-LC")[0]
    unit = Unit.objects.get_or_create(organization=org, code="шт", defaults={"name": "шт"})[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-LC-01", name="Цыпленок LC",
        category=cat, unit=unit,
    )


@pytest.fixture
def carcass_nom(org):
    cat = Category.objects.get_or_create(organization=org, name="ГП-LC")[0]
    unit_kg = Unit.objects.get_or_create(organization=org, code="кг", defaults={"name": "кг"})[0]
    item, _ = NomenclatureItem.objects.get_or_create(
        organization=org, sku="CARCASS-WHOLE",
        defaults={"name": "Тушка целая", "category": cat, "unit": unit_kg},
    )
    return item


@pytest.fixture
def batch(org, m_feedlot, m_slaughter, slaughter_line, chick_nom):
    return Batch.objects.create(
        organization=org, doc_number="ГLC-BATCH-01",
        nomenclature=chick_nom, unit=chick_nom.unit,
        origin_module=m_feedlot, current_module=m_slaughter,
        current_block=slaughter_line,
        current_quantity=Decimal("100"),
        initial_quantity=Decimal("100"),
        accumulated_cost_uzs=Decimal("1000000"),
        started_at=date.today(),
    )


@pytest.fixture
def shift(org, m_slaughter, slaughter_line, batch, user):
    return SlaughterShift.objects.create(
        organization=org, module=m_slaughter,
        line_block=slaughter_line, source_batch=batch,
        doc_number="ГLC-001", shift_date=date.today(),
        start_time=datetime.now(timezone.utc),
        live_heads_received=100,
        live_weight_kg_total=Decimal("250"),
        foreman=user,
    )


# ── ImmutableStatusMixin ────────────────────────────────────────────────


def test_immutable_mixin_blocks_update_when_posted(shift):
    """Меняем статус на posted напрямую (через .save()) → ViewSet.update должен запретить."""
    from apps.slaughter.views import SlaughterShiftViewSet

    shift.status = SlaughterShift.Status.POSTED
    shift.save()
    vs = SlaughterShiftViewSet()
    # Симулируем serializer.instance
    class FakeSerializer:
        instance = shift

    from rest_framework.exceptions import PermissionDenied
    with pytest.raises(PermissionDenied):
        vs.perform_update(FakeSerializer())


def test_immutable_mixin_blocks_destroy_when_posted(shift):
    from apps.slaughter.views import SlaughterShiftViewSet
    from rest_framework.exceptions import PermissionDenied

    shift.status = SlaughterShift.Status.POSTED
    shift.save()
    vs = SlaughterShiftViewSet()
    vs.request = None  # для _write_audit нужен request, но мы проверяем что упадёт раньше
    with pytest.raises(PermissionDenied):
        vs.perform_destroy(shift)


def test_immutable_mixin_allows_update_when_active(shift):
    """ACTIVE — можно обновлять."""
    from apps.slaughter.views import SlaughterShiftViewSet

    assert shift.status == SlaughterShift.Status.ACTIVE
    vs = SlaughterShiftViewSet()
    vs._check_mutable(shift)  # не должен бросить


def test_immutable_mixin_blocks_cancelled(shift):
    from apps.slaughter.views import SlaughterShiftViewSet
    from rest_framework.exceptions import PermissionDenied

    shift.status = SlaughterShift.Status.CANCELLED
    shift.save()
    vs = SlaughterShiftViewSet()
    with pytest.raises(PermissionDenied):
        vs._check_mutable(shift)


# ── DeleteReasonMixin ──────────────────────────────────────────────────


def test_delete_reason_mixin_requires_reason(shift, carcass_nom):
    """Без reason — ValidationError."""
    from apps.slaughter.views import SlaughterYieldViewSet
    from rest_framework.exceptions import ValidationError as DRFValidationError

    unit_kg = Unit.objects.get(organization=shift.organization, code="кг")
    y = SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("100"),
    )

    vs = SlaughterYieldViewSet()

    class FakeRequest:
        data = {}
        query_params = {}
    vs.request = FakeRequest()

    with pytest.raises(DRFValidationError):
        vs.perform_destroy(y)


def test_delete_reason_mixin_accepts_reason_in_body(shift, carcass_nom):
    """С body.reason — удаляет нормально."""
    from apps.slaughter.views import SlaughterYieldViewSet
    from apps.audit.models import AuditLog

    unit_kg = Unit.objects.get(organization=shift.organization, code="кг")
    y = SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("100"),
    )
    y_id = y.id

    vs = SlaughterYieldViewSet()

    class FakeRequest:
        data = {"reason": "опечатка в количестве"}
        query_params = {}
        user = None
        META: dict = {}
    vs.request = FakeRequest()

    vs.perform_destroy(y)
    assert not SlaughterYield.objects.filter(id=y_id).exists()


def test_delete_reason_mixin_accepts_reason_in_query(shift, carcass_nom):
    """С ?reason=... в query."""
    from apps.slaughter.views import SlaughterYieldViewSet

    unit_kg = Unit.objects.get(organization=shift.organization, code="кг")
    y = SlaughterYield.objects.create(
        shift=shift, nomenclature=carcass_nom, unit=unit_kg,
        quantity=Decimal("100"),
    )

    vs = SlaughterYieldViewSet()

    class FakeRequest:
        data = {}
        query_params = {"reason": "ошибка ввода"}
        user = None
        META: dict = {}
    vs.request = FakeRequest()

    vs.perform_destroy(y)
    assert not SlaughterYield.objects.filter(id=y.id).exists()
