"""
API-integration тесты для маточника:
  - GET timeline / stats — base shape + RBAC по деньгам
  - field-level RBAC: feed-cost скрыт у юзера без feed/ledger
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.matochnik.models import (
    BreedingFeedConsumption,
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from apps.warehouses.models import ProductionBlock


pytestmark = pytest.mark.django_db


# ─── fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def m_feed():
    return Module.objects.get(code="feed")


@pytest.fixture
def m_ledger():
    return Module.objects.get(code="ledger")


def _make_user(email, *, org, modules):
    u = User.objects.create(email=email, full_name=email)
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    for module, level in modules.items():
        UserModuleAccessOverride.objects.create(
            membership=membership, module=module, level=level,
        )
    return u


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def block(org, m_matochnik):
    return ProductionBlock.objects.create(
        organization=org, module=m_matochnik,
        code="K-API", name="Корпус API",
        kind=ProductionBlock.Kind.MATOCHNIK,
    )


@pytest.fixture
def herd(org, m_matochnik, block):
    user = User.objects.create(email="tech-api@y.local", full_name="Tech")
    return BreedingHerd.objects.create(
        organization=org, module=m_matochnik, block=block,
        doc_number="API-СТ-1",
        direction=BreedingHerd.Direction.BROILER_PARENT,
        placed_at=date.today() - timedelta(days=30),
        age_weeks_at_placement=22,
        initial_heads=10000, current_heads=9800,
        status=BreedingHerd.Status.PRODUCING,
        technologist=user,
    )


@pytest.fixture
def feed_records(herd):
    """Несколько записей разного типа в окне `today - 7..today`."""
    today = date.today()
    DailyEggProduction.objects.create(
        herd=herd, date=today, eggs_collected=8000, unfit_eggs=100,
    )
    BreedingMortality.objects.create(
        herd=herd, date=today, dead_count=5,
    )
    BreedingFeedConsumption.objects.create(
        herd=herd, date=today, quantity_kg=Decimal("500"),
    )


# ─── Timeline ────────────────────────────────────────────────────────────


def test_timeline_returns_events_for_matochnik_user(
    org, m_matochnik, herd, feed_records,
):
    """matochnik.r видит таймлайн (без денег — нет feed/ledger)."""
    u = _make_user("m-only@y.local", org=org, modules={m_matochnik: AccessLevel.READ})
    api = _client(u)
    resp = api.get(f"/api/matochnik/herds/{herd.id}/timeline/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "events" in body
    assert "counts" in body
    assert body["_finances_visible"] is False
    types = {ev["type"] for ev in body["events"]}
    assert "egg" in types
    assert "mortality" in types


def test_timeline_feed_cost_hidden_without_finance_access(
    org, m_matochnik, herd, feed_records,
):
    """В feed-событиях cost_uzs = None для юзера без feed/ledger."""
    u = _make_user("m-only2@y.local", org=org, modules={m_matochnik: AccessLevel.READ})
    api = _client(u)
    body = api.get(f"/api/matochnik/herds/{herd.id}/timeline/").json()
    feed_events = [ev for ev in body["events"] if ev["type"] == "feed"]
    assert feed_events
    for ev in feed_events:
        assert ev.get("cost_uzs") is None


def test_timeline_finances_visible_with_ledger_access(
    org, m_matochnik, m_ledger, herd, feed_records,
):
    """Юзер с ledger.r — `_finances_visible=True` (даже без реальных cost-данных)."""
    u = _make_user(
        "m-with-ledger@y.local", org=org,
        modules={m_matochnik: AccessLevel.READ, m_ledger: AccessLevel.READ},
    )
    api = _client(u)
    body = api.get(f"/api/matochnik/herds/{herd.id}/timeline/").json()
    assert body["_finances_visible"] is True


# ─── Stats ───────────────────────────────────────────────────────────────


def test_stats_shape(org, m_matochnik, herd, feed_records):
    u = _make_user("m-stats@y.local", org=org, modules={m_matochnik: AccessLevel.READ})
    api = _client(u)
    resp = api.get(f"/api/matochnik/herds/{herd.id}/stats/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    for k in [
        "days", "from", "to",
        "productivity_avg_pct", "productivity_today_pct",
        "eggs_total_clean", "mortality_total",
        "feed_total_kg", "feed_cost_total_uzs",
        "fcr", "egg_weight_g", "active_withdrawal_until",
        "series", "_finances_visible",
    ]:
        assert k in body, f"Отсутствует ключ {k}"
    assert body["_finances_visible"] is False
    # без feed/ledger — feed_cost_total_uzs замаскирован
    assert body["feed_cost_total_uzs"] is None


def test_stats_feed_cost_visible_with_ledger(
    org, m_matochnik, m_ledger, herd, feed_records,
):
    u = _make_user(
        "m-stats-l@y.local", org=org,
        modules={m_matochnik: AccessLevel.READ, m_ledger: AccessLevel.READ},
    )
    api = _client(u)
    body = api.get(f"/api/matochnik/herds/{herd.id}/stats/").json()
    assert body["_finances_visible"] is True
    # feed_cost_total_uzs — строка (даже если 0, мы её формируем)
    assert isinstance(body["feed_cost_total_uzs"], str)


# ─── BreedingFeedConsumptionSerializer field-level RBAC ──────────────────


def test_feed_consumption_serializer_hides_cost_for_matochnik_only_user(
    org, m_matochnik, herd,
):
    """matochnik.r без feed/ledger — unit_cost_uzs/total_cost_uzs == None."""
    BreedingFeedConsumption.objects.create(
        herd=herd, date=date.today(), quantity_kg=Decimal("100"),
    )
    u = _make_user("m-fc@y.local", org=org, modules={m_matochnik: AccessLevel.READ})
    api = _client(u)
    resp = api.get(f"/api/matochnik/feed-consumption/?herd={herd.id}")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    items = data.get("results", data) if isinstance(data, dict) else data
    assert len(items) >= 1
    item = items[0]
    assert item["unit_cost_uzs"] is None
    assert item["total_cost_uzs"] is None
    assert item["_finances_visible"] is False


def test_feed_consumption_serializer_shows_cost_for_feed_user(
    org, m_matochnik, m_feed, herd,
):
    """feed.r — деньги видны (свой модуль-владелец)."""
    BreedingFeedConsumption.objects.create(
        herd=herd, date=date.today(), quantity_kg=Decimal("100"),
    )
    u = _make_user(
        "m-fc-feed@y.local", org=org,
        modules={m_matochnik: AccessLevel.READ, m_feed: AccessLevel.READ},
    )
    api = _client(u)
    resp = api.get(f"/api/matochnik/feed-consumption/?herd={herd.id}")
    body = resp.json()
    items = body.get("results", body) if isinstance(body, dict) else body
    assert items[0]["_finances_visible"] is True
