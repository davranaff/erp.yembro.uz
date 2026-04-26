"""
Тесты release_raw_material_quarantine + release_feed_passport.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount
from apps.counterparties.models import Counterparty
from apps.feed.models import (
    FeedBatch,
    LabResult,
    ProductionTask,
    RawMaterialBatch,
    Recipe,
    RecipeVersion,
)
from apps.feed.services.quality import (
    FeedQualityServiceError,
    release_feed_passport,
    release_raw_material_quarantine,
)
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization
from apps.users.models import User
from apps.warehouses.models import ProductionBlock, Warehouse


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def user():
    return User.objects.create(email="q@y.local", full_name="Q")


@pytest.fixture
def unit_kg(org):
    return Unit.objects.get_or_create(
        organization=org, code="кг", defaults={"name": "кг"}
    )[0]


@pytest.fixture
def cat_raw(org):
    sub = GLSubaccount.objects.get(account__organization=org, code="10.01")
    return Category.objects.get_or_create(
        organization=org, name="Корма сырьё",
        defaults={"default_gl_subaccount": sub},
    )[0]


@pytest.fixture
def corn(org, cat_raw, unit_kg):
    return NomenclatureItem.objects.create(
        organization=org, sku="С-КУК-01", name="Кукуруза",
        category=cat_raw, unit=unit_kg,
    )


@pytest.fixture
def supplier(org):
    return Counterparty.objects.create(
        organization=org, code="К-S", kind="supplier", name="S"
    )


@pytest.fixture
def wh(org, m_feed):
    return Warehouse.objects.create(
        organization=org, module=m_feed, code="СК-СР", name="Сырьё"
    )


@pytest.fixture
def raw_batch(org, m_feed, corn, supplier, wh, unit_kg):
    return RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-Q1",
        nomenclature=corn, supplier=supplier, warehouse=wh,
        received_date=date.today(),
        quantity=Decimal("1000"), current_quantity=Decimal("1000"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000"),
        status=RawMaterialBatch.Status.QUARANTINE,
    )


# ─── Raw material quarantine release ─────────────────────────────────────


def test_release_raw_passed_moves_to_available(org, raw_batch):
    lab = LabResult.objects.create(
        organization=org,
        doc_number="ЛА-001",
        subject_content_type=ContentType.objects.get_for_model(RawMaterialBatch),
        subject_object_id=raw_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PASSED,
    )
    release_raw_material_quarantine(raw_batch, lab_result=lab)
    raw_batch.refresh_from_db()
    assert raw_batch.status == RawMaterialBatch.Status.AVAILABLE


def test_release_raw_failed_moves_to_rejected(org, raw_batch):
    lab = LabResult.objects.create(
        organization=org,
        doc_number="ЛА-002",
        subject_content_type=ContentType.objects.get_for_model(RawMaterialBatch),
        subject_object_id=raw_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.FAILED,
        notes="Высокая влажность",
    )
    release_raw_material_quarantine(raw_batch, lab_result=lab)
    raw_batch.refresh_from_db()
    assert raw_batch.status == RawMaterialBatch.Status.REJECTED
    assert "влажность" in raw_batch.rejection_reason.lower()


def test_release_raw_pending_raises(org, raw_batch):
    lab = LabResult.objects.create(
        organization=org,
        doc_number="ЛА-003",
        subject_content_type=ContentType.objects.get_for_model(RawMaterialBatch),
        subject_object_id=raw_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PENDING,
    )
    with pytest.raises(ValidationError):
        release_raw_material_quarantine(raw_batch, lab_result=lab)


def test_release_raw_wrong_subject_raises(org, raw_batch, corn, supplier, wh, unit_kg, m_feed):
    other = RawMaterialBatch.objects.create(
        organization=org, module=m_feed, doc_number="П-К-OTHER",
        nomenclature=corn, supplier=supplier, warehouse=wh,
        received_date=date.today(),
        quantity=Decimal("500"), current_quantity=Decimal("500"),
        unit=unit_kg, price_per_unit_uzs=Decimal("18000"),
    )
    lab = LabResult.objects.create(
        organization=org,
        doc_number="ЛА-004",
        subject_content_type=ContentType.objects.get_for_model(RawMaterialBatch),
        subject_object_id=other.id,  # другой batch!
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PASSED,
    )
    with pytest.raises(ValidationError):
        release_raw_material_quarantine(raw_batch, lab_result=lab)


def test_release_raw_not_in_quarantine_raises(org, raw_batch):
    raw_batch.status = RawMaterialBatch.Status.AVAILABLE
    raw_batch.save()
    lab = LabResult.objects.create(
        organization=org,
        doc_number="ЛА-005",
        subject_content_type=ContentType.objects.get_for_model(RawMaterialBatch),
        subject_object_id=raw_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PASSED,
    )
    with pytest.raises(ValidationError):
        release_raw_material_quarantine(raw_batch, lab_result=lab)


# ─── Feed passport release ────────────────────────────────────────────────


@pytest.fixture
def recipe(org):
    return Recipe.objects.create(
        organization=org, code="Р-Q", name="Q", direction="broiler"
    )


@pytest.fixture
def recipe_version(recipe):
    return RecipeVersion.objects.create(
        recipe=recipe, version_number=1,
        status="active", effective_from=date(2026, 1, 1),
    )


@pytest.fixture
def mixer_line(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="СМ-Q",
        name="Q", kind=ProductionBlock.Kind.MIXER_LINE,
    )


@pytest.fixture
def storage_bin(org, m_feed):
    return ProductionBlock.objects.create(
        organization=org, module=m_feed, code="БН-Q",
        name="Q", kind=ProductionBlock.Kind.STORAGE_BIN,
    )


@pytest.fixture
def task(org, m_feed, recipe_version, mixer_line, user):
    return ProductionTask.objects.create(
        organization=org, module=m_feed, doc_number="ЗП-Q",
        recipe_version=recipe_version, production_line=mixer_line,
        shift="day",
        scheduled_at=datetime.now(timezone.utc),
        planned_quantity_kg=Decimal("100"),
        status="done",
        actual_quantity_kg=Decimal("100"),
        completed_at=datetime.now(timezone.utc),
        technologist=user,
    )


@pytest.fixture
def feed_batch(org, m_feed, task, recipe_version, storage_bin):
    return FeedBatch.objects.create(
        organization=org, module=m_feed, doc_number="К-Q-001",
        produced_by_task=task, recipe_version=recipe_version,
        produced_at=datetime.now(timezone.utc),
        quantity_kg=Decimal("100"), current_quantity_kg=Decimal("100"),
        unit_cost_uzs=Decimal("5000"), total_cost_uzs=Decimal("500000"),
        storage_bin=storage_bin,
        status=FeedBatch.Status.QUALITY_CHECK,
        quality_passport_status=FeedBatch.PassportStatus.PENDING,
    )


def test_release_feed_passed(org, feed_batch):
    lab = LabResult.objects.create(
        organization=org, doc_number="ЛА-FB-001",
        subject_content_type=ContentType.objects.get_for_model(FeedBatch),
        subject_object_id=feed_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PASSED,
    )
    release_feed_passport(feed_batch, lab_result=lab)
    feed_batch.refresh_from_db()
    assert feed_batch.status == FeedBatch.Status.APPROVED
    assert feed_batch.quality_passport_status == FeedBatch.PassportStatus.PASSED


def test_release_feed_failed(org, feed_batch):
    lab = LabResult.objects.create(
        organization=org, doc_number="ЛА-FB-002",
        subject_content_type=ContentType.objects.get_for_model(FeedBatch),
        subject_object_id=feed_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.FAILED,
    )
    release_feed_passport(feed_batch, lab_result=lab)
    feed_batch.refresh_from_db()
    assert feed_batch.status == FeedBatch.Status.REJECTED
    assert feed_batch.quality_passport_status == FeedBatch.PassportStatus.FAILED


def test_release_feed_already_rejected_raises(org, feed_batch):
    feed_batch.status = FeedBatch.Status.REJECTED
    feed_batch.save()
    lab = LabResult.objects.create(
        organization=org, doc_number="ЛА-FB-003",
        subject_content_type=ContentType.objects.get_for_model(FeedBatch),
        subject_object_id=feed_batch.id,
        sampled_at=datetime.now(timezone.utc),
        status=LabResult.Status.PASSED,
    )
    with pytest.raises(ValidationError):
        release_feed_passport(feed_batch, lab_result=lab)
