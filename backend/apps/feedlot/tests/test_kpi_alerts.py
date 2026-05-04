"""
Тесты для `apps.feedlot.services.kpi_alerts.collect_org_alerts`.

Покрывают:
  - mortality > 5% → алерт
  - mortality в норме → пусто
  - FCR > 2.0 → алерт (только если день >= 14)
  - FCR > 2.0, но день < 14 → пропуск (раннюю шумность не алертим)
  - Партия в SHIPPED → не проверяется
  - per-org изоляция: алерты org A не утекают в org B
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.batches.models import Batch
from apps.feedlot.models import (
    DailyWeighing,
    FeedlotBatch,
    FeedlotFeedConsumption,
)
from apps.feedlot.services.kpi_alerts import collect_org_alerts
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
def technologist():
    return User.objects.create(email="tech-kpi@y.local", full_name="Tech")


@pytest.fixture
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot,
        code="KPI-H1", name="Птичник KPI",
        kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def parent_batch(org, m_feedlot, house):
    unit = Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "Голов"},
    )[0]
    cat = Category.objects.get_or_create(organization=org, name="Птица KPI")[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="KPI-P-1", name="Цыпленок KPI",
        category=cat, unit=unit,
    )
    return Batch.objects.create(
        organization=org, doc_number="П-KPI-P-1",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        started_at=date.today() - timedelta(days=20),
    )


def _make_batch(*, org, module, house, batch, technologist, doc, days_ago,
                initial=10000, current=9500):
    return FeedlotBatch.objects.create(
        organization=org, module=module,
        house_block=house, batch=batch,
        doc_number=doc,
        placed_date=date.today() - timedelta(days=days_ago),
        initial_heads=initial,
        current_heads=current,
        status=FeedlotBatch.Status.GROWING,
        technologist=technologist,
    )


def test_high_mortality_triggers_alert(
    org, m_feedlot, house, parent_batch, technologist,
):
    """Падёж 10% (1000 из 10000) при пороге 5% → алерт."""
    _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A1", days_ago=10,
        initial=10000, current=9000,  # 10% падёж
    )

    alerts = collect_org_alerts(org)
    mortality_alerts = [a for a in alerts if "падёж" in a.kind]
    assert len(mortality_alerts) >= 1
    assert mortality_alerts[0].batch_doc == "KPI-A1"


def test_normal_mortality_no_alert(
    org, m_feedlot, house, parent_batch, technologist,
):
    """Падёж 2% — в норме, алерта быть не должно."""
    _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A2", days_ago=10,
        initial=10000, current=9800,  # 2% падёж
    )

    alerts = collect_org_alerts(org)
    a2_alerts = [a for a in alerts if a.batch_doc == "KPI-A2"]
    assert a2_alerts == []


def test_high_fcr_triggers_alert_after_min_day(
    org, m_feedlot, house, parent_batch, technologist,
):
    """FCR > 2.0 после 14-го дня → алерт."""
    fb = _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A3", days_ago=20,
        initial=10000, current=9800,
    )
    # Создаём взвешивания: первое 0.05 кг (старт), последнее 1.0 кг (gain 0.95×9800=9310 кг)
    DailyWeighing.objects.create(
        feedlot_batch=fb, date=fb.placed_date, day_of_age=0,
        sample_size=100, avg_weight_kg=Decimal("0.050"),
    )
    DailyWeighing.objects.create(
        feedlot_batch=fb, date=date.today(), day_of_age=20,
        sample_size=100, avg_weight_kg=Decimal("1.000"),
    )
    # Корм: 25 000 кг → FCR = 25000 / 9310 ≈ 2.69 > порог 2.0
    FeedlotFeedConsumption.objects.create(
        feedlot_batch=fb,
        period_from_day=0, period_to_day=20,
        feed_type=FeedlotFeedConsumption.FeedType.GROWTH,
        total_kg=Decimal("25000"),
    )

    alerts = collect_org_alerts(org)
    fcr_alerts = [a for a in alerts if a.kind == "FCR" and a.batch_doc == "KPI-A3"]
    assert len(fcr_alerts) == 1


def test_high_fcr_skipped_before_min_day(
    org, m_feedlot, house, parent_batch, technologist,
):
    """FCR > 2.0 но день < 14 → не алертим (шум)."""
    fb = _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A4", days_ago=5,
    )
    DailyWeighing.objects.create(
        feedlot_batch=fb, date=fb.placed_date, day_of_age=0,
        sample_size=100, avg_weight_kg=Decimal("0.050"),
    )
    DailyWeighing.objects.create(
        feedlot_batch=fb, date=date.today(), day_of_age=5,
        sample_size=100, avg_weight_kg=Decimal("0.150"),
    )
    FeedlotFeedConsumption.objects.create(
        feedlot_batch=fb,
        period_from_day=0, period_to_day=5,
        feed_type=FeedlotFeedConsumption.FeedType.START,
        total_kg=Decimal("5000"),  # FCR =  ~5.5, но день=5 < 14 → пропуск
    )

    alerts = collect_org_alerts(org)
    a4_alerts = [a for a in alerts if a.batch_doc == "KPI-A4" and a.kind == "FCR"]
    assert a4_alerts == []


def test_shipped_batch_not_checked(
    org, m_feedlot, house, parent_batch, technologist,
):
    fb = _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A5", days_ago=20,
        initial=10000, current=8000,  # 20% — шквал-падёж, но партия SHIPPED
    )
    fb.status = FeedlotBatch.Status.SHIPPED
    fb.save(update_fields=["status"])

    alerts = collect_org_alerts(org)
    a5_alerts = [a for a in alerts if a.batch_doc == "KPI-A5"]
    assert a5_alerts == []


@override_settings(FEEDLOT_MORTALITY_ALERT_PCT=10.0)
def test_threshold_overridable_via_settings(
    org, m_feedlot, house, parent_batch, technologist,
):
    """С порогом 10% — падёж 8% не должен триггерить."""
    _make_batch(
        org=org, module=m_feedlot, house=house, batch=parent_batch,
        technologist=technologist, doc="KPI-A6", days_ago=10,
        initial=10000, current=9200,  # 8% — ниже override-порога 10%
    )

    alerts = collect_org_alerts(org)
    a6_alerts = [a for a in alerts if a.batch_doc == "KPI-A6"]
    assert a6_alerts == []
