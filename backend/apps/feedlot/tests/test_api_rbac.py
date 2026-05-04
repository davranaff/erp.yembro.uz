"""
API-RBAC тесты для feedlot:
  - POST /batches/{id}/mortality/ → loss_amount_uzs скрыт без feedlot/ledger
  - POST /batches/{id}/feed_consumption/ → amount_uzs скрыт без feed/ledger
  - С ledger.r — деньги видны (общефинансовый bypass)

Минимальные fixtures: переиспользуем приватные хелперы вместо полной
фабрики feed_batch + chart_of_accounts (это покрыто service-тестами).
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.batches.models import Batch
from apps.feedlot.models import FeedlotBatch
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
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
def m_feedlot():
    return Module.objects.get(code="feedlot")


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
def house(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot,
        code="ПТ-RBAC-1", name="Птичник RBAC",
        kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def chick_batch(org, m_feedlot, house):
    unit = Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "Голов"},
    )[0]
    cat = Category.objects.get_or_create(organization=org, name="Птица RBAC")[0]
    nom = NomenclatureItem.objects.create(
        organization=org, sku="RBAC-БР-1", name="Бройлер RBAC",
        category=cat, unit=unit,
    )
    return Batch.objects.create(
        organization=org, doc_number="П-RBAC-1",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=house,
        current_quantity=Decimal("10000"),
        initial_quantity=Decimal("10000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date(2026, 4, 1),
    )


@pytest.fixture
def feedlot_batch(org, m_feedlot, house, chick_batch):
    user = User.objects.create(email="rbac-tech@y.local", full_name="Tech")
    return FeedlotBatch.objects.create(
        organization=org, module=m_feedlot,
        house_block=house, batch=chick_batch,
        doc_number="ФЛ-RBAC-1", placed_date=date(2026, 4, 1),
        target_weight_kg=Decimal("2.500"),
        initial_heads=10000, current_heads=10000,
        status=FeedlotBatch.Status.GROWING,
        technologist=user,
    )


# ─── Mortality action — RBAC ─────────────────────────────────────────────


def test_mortality_action_hides_loss_amount_for_user_without_ledger(
    org, m_feedlot, feedlot_batch,
):
    """feedlot.rw, нет ledger → loss_amount_uzs/journal_entry_doc=null."""
    u = _make_user(
        "rbac-fl-rw@y.local", org=org,
        modules={m_feedlot: AccessLevel.READ_WRITE},
    )
    api = _client(u)
    resp = api.post(
        f"/api/feedlot/batches/{feedlot_batch.id}/mortality/",
        {"date": "2026-04-15", "day_of_age": 14, "dead_count": 50, "cause": "тест"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    res = body.get("_result", {})
    assert res["loss_amount_uzs"] is None
    assert res["journal_entry_doc"] is None
    assert res["_finances_visible"] is False


def test_mortality_action_shows_loss_amount_with_ledger(
    org, m_feedlot, m_ledger, feedlot_batch,
):
    """feedlot.rw + ledger.r → loss_amount_uzs виден."""
    u = _make_user(
        "rbac-fl-led@y.local", org=org,
        modules={m_feedlot: AccessLevel.READ_WRITE, m_ledger: AccessLevel.READ},
    )
    api = _client(u)
    resp = api.post(
        f"/api/feedlot/batches/{feedlot_batch.id}/mortality/",
        {"date": "2026-04-16", "day_of_age": 15, "dead_count": 30, "cause": "тест"},
        format="json",
    )
    body = resp.json()
    res = body.get("_result", {})
    # loss_amount_uzs — строка с числом (cost × dead_count)
    assert res["loss_amount_uzs"] is not None
    assert res["_finances_visible"] is True
