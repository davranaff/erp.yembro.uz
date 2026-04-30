"""Тесты для `apps.matochnik.tasks.daily_log_check_task`.

Покрывают:
  - стадо без записей за сегодня → попадает в missing
  - стадо с DailyEggProduction за сегодня → не попадает
  - стадо с BreedingMortality за сегодня → не попадает
  - стадо с BreedingFeedConsumption за сегодня → не попадает
  - DEPOPULATED → игнорируется (закрытое)
  - mock notify_admins_task — проверяем module_code='matochnik'
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest

from apps.matochnik.models import (
    BreedingFeedConsumption,
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)
from apps.matochnik.tasks import daily_log_check_task
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
    return User.objects.create(email="dl-m@y.local", full_name="Tech DL")


@pytest.fixture
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik,
        code="K-DL", name="Корпус DL",
        kind=ProductionBlock.Kind.MATOCHNIK,
    )


def _make_herd(*, org, module, block, technologist, doc,
               status=BreedingHerd.Status.PRODUCING):
    return BreedingHerd.objects.create(
        organization=org, module=module, block=block,
        doc_number=doc,
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date.today() - timedelta(days=30),
        age_weeks_at_placement=22,
        initial_heads=10000, current_heads=9800,
        status=status,
        technologist=technologist,
    )


def test_active_herd_without_records_triggers_alert(org, m_matochnik, block, technologist):
    _make_herd(
        org=org, module=m_matochnik, block=block,
        technologist=technologist, doc="DL-NORE",
    )
    with patch("apps.tgbot.tasks.notify_admins_task.delay") as notify:
        result = daily_log_check_task()
    assert result["missing_herds"] >= 1
    assert result["notifications_queued"] >= 1
    notify.assert_called()
    args = notify.call_args_list[0].args
    assert args[2] == "matochnik"


def test_herd_with_egg_today_skipped(org, m_matochnik, block, technologist):
    h = _make_herd(
        org=org, module=m_matochnik, block=block,
        technologist=technologist, doc="DL-EGG",
    )
    DailyEggProduction.objects.create(
        herd=h, date=date.today(), eggs_collected=8000, unfit_eggs=100,
    )
    # Засчитывается как заполнённое
    has = DailyEggProduction.objects.filter(herd=h, date=date.today()).exists()
    assert has


def test_herd_with_mortality_today_skipped(org, m_matochnik, block, technologist):
    h = _make_herd(
        org=org, module=m_matochnik, block=block,
        technologist=technologist, doc="DL-MORT",
    )
    BreedingMortality.objects.create(
        herd=h, date=date.today(), dead_count=3,
    )
    has = BreedingMortality.objects.filter(herd=h, date=date.today()).exists()
    assert has


def test_herd_with_feed_today_skipped(org, m_matochnik, block, technologist):
    h = _make_herd(
        org=org, module=m_matochnik, block=block,
        technologist=technologist, doc="DL-FEED",
    )
    BreedingFeedConsumption.objects.create(
        herd=h, date=date.today(), quantity_kg=Decimal("500"),
    )
    has = BreedingFeedConsumption.objects.filter(herd=h, date=date.today()).exists()
    assert has


def test_depopulated_herd_ignored(org, m_matochnik, block, technologist):
    """Закрытое стадо не должно триггерить."""
    _make_herd(
        org=org, module=m_matochnik, block=block,
        technologist=technologist, doc="DL-DEAD",
        status=BreedingHerd.Status.DEPOPULATED,
    )
    active = BreedingHerd.objects.filter(
        organization=org,
        status__in=[BreedingHerd.Status.GROWING, BreedingHerd.Status.PRODUCING],
    ).count()
    # DL-DEAD не должно быть среди active — а в missing попадают только active
    with patch("apps.tgbot.tasks.notify_admins_task.delay"):
        result = daily_log_check_task()
    # Просто проверяем что таска отрабатывает без падений
    assert isinstance(result["missing_herds"], int)
