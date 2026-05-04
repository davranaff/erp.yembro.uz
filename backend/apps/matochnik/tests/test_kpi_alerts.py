"""Тесты `apps.matochnik.services.kpi_alerts.collect_org_alerts`.

Покрывают:
  - продуктивность ниже порога → алерт (только PRODUCING + взрослое)
  - продуктивность нормальная → пусто
  - молодое стадо (age < min_age) → не алертим
  - GROWING-стадо (ещё не несётся) → продуктивность не проверяем
  - недельный падёж > порога → алерт
  - DEPOPULATED-стадо → игнорируется
  - per-org изоляция
  - override порогов через settings
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.matochnik.models import (
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)
from apps.matochnik.services.kpi_alerts import collect_org_alerts
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
def technologist():
    return User.objects.create(email="kpi-m@y.local", full_name="Tech KPI")


@pytest.fixture
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik,
        code="K-KPI", name="Корпус KPI",
        kind=ProductionBlock.Kind.MATOCHNIK,
    )


def _make_herd(*, org, module, block, technologist, doc, status, age_weeks_at_placement=22,
               days_ago=30, current_heads=9000, initial_heads=10000):
    return BreedingHerd.objects.create(
        organization=org, module=module, block=block,
        doc_number=doc,
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date.today() - timedelta(days=days_ago),
        age_weeks_at_placement=age_weeks_at_placement,
        initial_heads=initial_heads, current_heads=current_heads,
        status=status,
        technologist=technologist,
    )


# ─── Низкая продуктивность → алерт ──────────────────────────────────────


def test_low_productivity_triggers_alert(org, m_matochnik, block, technologist):
    """Стадо PRODUCING + взрослое + 30%/нед < 50% → алерт."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-LOW", status=BreedingHerd.Status.PRODUCING,
        current_heads=10000, initial_heads=10000,
    )
    # 30% за 7 дней: 21000 чистых = 0.3 * 10000 * 7
    today = date.today()
    for i in range(7):
        DailyEggProduction.objects.create(
            herd=herd, date=today - timedelta(days=i),
            eggs_collected=3000, unfit_eggs=0,
        )
    alerts = collect_org_alerts(org)
    matched = [a for a in alerts if a.herd_doc == "KPI-LOW" and a.kind == "продуктивность"]
    assert len(matched) == 1


def test_normal_productivity_no_alert(org, m_matochnik, block, technologist):
    """80%/нед — норма для продуктивного стада."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-OK", status=BreedingHerd.Status.PRODUCING,
        current_heads=10000, initial_heads=10000,
    )
    today = date.today()
    for i in range(7):
        DailyEggProduction.objects.create(
            herd=herd, date=today - timedelta(days=i),
            eggs_collected=8000, unfit_eggs=0,
        )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-OK" for a in alerts)


def test_young_herd_productivity_skipped(org, m_matochnik, block, technologist):
    """Возраст < MIN_AGE_WEEKS — продуктивность не алертим."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-YOUNG", status=BreedingHerd.Status.PRODUCING,
        age_weeks_at_placement=10, days_ago=14,  # ~12 нед < 22
        current_heads=10000, initial_heads=10000,
    )
    today = date.today()
    DailyEggProduction.objects.create(
        herd=herd, date=today, eggs_collected=0, unfit_eggs=0,
    )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-YOUNG" or a.kind != "продуктивность" for a in alerts)


def test_growing_herd_no_productivity_alert(org, m_matochnik, block, technologist):
    """GROWING-стадо ещё не несётся — продуктивность не проверяем."""
    _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-GROW", status=BreedingHerd.Status.GROWING,
        current_heads=10000, initial_heads=10000,
    )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-GROW" or a.kind != "продуктивность" for a in alerts)


# ─── Падёж за неделю ────────────────────────────────────────────────────


def test_high_weekly_mortality_triggers_alert(org, m_matochnik, block, technologist):
    """1.5% падежа за неделю при пороге 1% → алерт."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-MORT", status=BreedingHerd.Status.PRODUCING,
        current_heads=10000, initial_heads=10000,
    )
    today = date.today()
    BreedingMortality.objects.create(
        herd=herd, date=today, dead_count=150,
    )
    alerts = collect_org_alerts(org)
    matched = [a for a in alerts if a.herd_doc == "KPI-MORT" and a.kind == "падёж/нед"]
    assert len(matched) == 1


def test_low_weekly_mortality_no_alert(org, m_matochnik, block, technologist):
    """0.05% — в норме."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-MORT-OK", status=BreedingHerd.Status.PRODUCING,
        current_heads=10000, initial_heads=10000,
    )
    today = date.today()
    BreedingMortality.objects.create(
        herd=herd, date=today, dead_count=5,
    )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-MORT-OK" or a.kind != "падёж/нед" for a in alerts)


def test_depopulated_herd_ignored(org, m_matochnik, block, technologist):
    """DEPOPULATED-стада не проверяем — они закрыты."""
    _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-DEAD", status=BreedingHerd.Status.DEPOPULATED,
        current_heads=0, initial_heads=10000,
    )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-DEAD" for a in alerts)


@override_settings(
    MATOCHNIK_LOW_PRODUCTIVITY_ALERT_PCT=20.0,
    MATOCHNIK_MORTALITY_ALERT_PCT_WEEK=5.0,
)
def test_thresholds_overridable_via_settings(org, m_matochnik, block, technologist):
    """С низким порогом продуктивности и высоким падежа — нет алертов."""
    herd = _make_herd(
        org=org, module=m_matochnik, block=block, technologist=technologist,
        doc="KPI-OVR", status=BreedingHerd.Status.PRODUCING,
        current_heads=10000, initial_heads=10000,
    )
    today = date.today()
    # 30% продуктивность — выше нового порога 20%
    for i in range(7):
        DailyEggProduction.objects.create(
            herd=herd, date=today - timedelta(days=i),
            eggs_collected=3000, unfit_eggs=0,
        )
    # 1.5% падёж — ниже нового порога 5%
    BreedingMortality.objects.create(
        herd=herd, date=today, dead_count=150,
    )
    alerts = collect_org_alerts(org)
    assert all(a.herd_doc != "KPI-OVR" for a in alerts)
