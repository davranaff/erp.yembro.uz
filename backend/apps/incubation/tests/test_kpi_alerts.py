"""
Тесты для `apps.incubation.services.kpi_alerts.collect_org_alerts`.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.batches.models import Batch
from apps.incubation.models import IncubationRun
from apps.incubation.services.kpi_alerts import collect_org_alerts
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
def m_inc():
    return Module.objects.get(code="incubation")


@pytest.fixture
def technologist():
    return User.objects.create(email="inc-kpi@y.local", full_name="Tech")


@pytest.fixture
def incubator(org, m_inc):
    return ProductionBlock.objects.create(
        organization=org, module=m_inc,
        code="INC-K", name="Инкубатор KPI",
        kind=ProductionBlock.Kind.INCUBATION,
    )


@pytest.fixture
def parent_batch(org, m_inc, incubator):
    unit = Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штук"},
    )[0]
    cat = Category.objects.get_or_create(organization=org, name="Яйцо KPI")[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="INC-K-1", name="Яйца инкуб. KPI",
        category=cat, unit=unit,
    )
    return Batch.objects.create(
        organization=org, doc_number="П-INC-K-1",
        nomenclature=nom, unit=unit,
        origin_module=m_inc, current_module=m_inc,
        current_block=incubator,
        current_quantity=Decimal("1000"),
        initial_quantity=Decimal("1100"),
        started_at=date.today() - timedelta(days=21),
    )


def _make_run(*, org, m_inc, incubator, batch, technologist, doc, hatched, fertile,
              hatch_date=None, status=IncubationRun.Status.TRANSFERRED):
    return IncubationRun.objects.create(
        organization=org, module=m_inc,
        incubator_block=incubator, batch=batch,
        doc_number=doc,
        loaded_date=date.today() - timedelta(days=21),
        expected_hatch_date=date.today(),
        actual_hatch_date=hatch_date or date.today(),
        eggs_loaded=fertile + 100,
        fertile_eggs=fertile,
        hatched_count=hatched,
        status=status,
        technologist=technologist,
    )


def test_low_hatch_rate_triggers_alert(
    org, m_inc, incubator, parent_batch, technologist,
):
    """65/100 = 65% — ниже дефолта 80% → алерт."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-LOW",
        hatched=650, fertile=1000,  # 65%
    )
    alerts = collect_org_alerts(org)
    matched = [a for a in alerts if a.run_doc == "INC-LOW"]
    assert len(matched) == 1
    assert Decimal(matched[0].hatch_rate_pct) == Decimal("65.00")


def test_high_hatch_rate_no_alert(
    org, m_inc, incubator, parent_batch, technologist,
):
    """85% — норма, алерта быть не должно."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-HIGH",
        hatched=850, fertile=1000,
    )
    alerts = collect_org_alerts(org)
    matched = [a for a in alerts if a.run_doc == "INC-HIGH"]
    assert matched == []


def test_old_run_not_alerted(
    org, m_inc, incubator, parent_batch, technologist,
):
    """Партия закрыта 5 дней назад — окно «последние 24ч» уже прошло."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-OLD",
        hatched=500, fertile=1000,  # 50%, очень плохо но старый run
        hatch_date=date.today() - timedelta(days=5),
    )
    alerts = collect_org_alerts(org)
    assert all(a.run_doc != "INC-OLD" for a in alerts)


def test_small_batch_skipped_as_noisy(
    org, m_inc, incubator, parent_batch, technologist,
):
    """На малых партиях (< INCUBATION_MIN_FERTILE_FOR_ALERT=100) не алертим."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-SMALL",
        hatched=30, fertile=50,  # 60% — но fertile=50 < 100
    )
    alerts = collect_org_alerts(org)
    assert all(a.run_doc != "INC-SMALL" for a in alerts)


def test_unfinished_run_not_alerted(
    org, m_inc, incubator, parent_batch, technologist,
):
    """Партия в статусе INCUBATING (вывод ещё не сделан) не алертится."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-RUNNING",
        hatched=0, fertile=1000,
        status=IncubationRun.Status.INCUBATING,
    )
    alerts = collect_org_alerts(org)
    assert all(a.run_doc != "INC-RUNNING" for a in alerts)


@override_settings(INCUBATION_HATCH_RATE_ALERT_PCT=70.0)
def test_threshold_overridable_via_settings(
    org, m_inc, incubator, parent_batch, technologist,
):
    """С порогом 70% — 75% не должен триггерить."""
    _make_run(
        org=org, m_inc=m_inc, incubator=incubator, batch=parent_batch,
        technologist=technologist, doc="INC-OVR",
        hatched=750, fertile=1000,  # 75% > порог 70% → норма
    )
    alerts = collect_org_alerts(org)
    assert all(a.run_doc != "INC-OVR" for a in alerts)
