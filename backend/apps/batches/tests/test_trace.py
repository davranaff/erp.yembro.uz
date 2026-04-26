"""
Smoke-тест /api/batches/{id}/trace/.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.batches.models import Batch, BatchChainStep, BatchCostEntry
from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
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
def m_core():
    return Module.objects.get(code="core")


@pytest.fixture
def user(org, m_core):
    u = User.objects.create(email="trace@y.local", full_name="T")
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    UserModuleAccessOverride.objects.create(
        membership=membership, module=m_core, level=AccessLevel.READ,
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


@pytest.fixture
def unit(org):
    return Unit.objects.get_or_create(
        organization=org, code="гол", defaults={"name": "гол"}
    )[0]


@pytest.fixture
def cat(org):
    return Category.objects.get_or_create(organization=org, name="Птица")[0]


@pytest.fixture
def nom(org, cat, unit):
    return NomenclatureItem.objects.create(
        organization=org, sku="ЖП-Т-01", name="Цыпленок",
        category=cat, unit=unit,
    )


@pytest.fixture
def block(org, m_feedlot):
    return ProductionBlock.objects.create(
        organization=org, module=m_feedlot, code="ПТ-Т",
        name="П", kind=ProductionBlock.Kind.FEEDLOT,
    )


@pytest.fixture
def parent_batch(org, m_feedlot, block, nom, unit):
    return Batch.objects.create(
        organization=org, doc_number="П-РОД-01",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=block,
        current_quantity=Decimal("0"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("5000000"),
        started_at=date.today() - timedelta(days=40),
    )


@pytest.fixture
def batch(org, m_feedlot, block, nom, unit, parent_batch):
    b = Batch.objects.create(
        organization=org, doc_number="П-Т-01",
        nomenclature=nom, unit=unit,
        origin_module=m_feedlot, current_module=m_feedlot,
        current_block=block,
        current_quantity=Decimal("950"),
        initial_quantity=Decimal("1000"),
        accumulated_cost_uzs=Decimal("3000000"),
        started_at=date.today() - timedelta(days=10),
        parent_batch=parent_batch,
    )
    BatchChainStep.objects.create(
        batch=b, sequence=1, module=m_feedlot, block=block,
        entered_at=timezone.now() - timedelta(days=10),
        quantity_in=Decimal("1000"),
    )
    BatchCostEntry.objects.create(
        batch=b, category=BatchCostEntry.Category.FEED,
        amount_uzs=Decimal("1500000"), description="корм неделя 1",
        occurred_at=timezone.now() - timedelta(days=7), module=m_feedlot,
    )
    BatchCostEntry.objects.create(
        batch=b, category=BatchCostEntry.Category.VET,
        amount_uzs=Decimal("500000"), description="вакцинация",
        occurred_at=timezone.now() - timedelta(days=5), module=m_feedlot,
    )
    BatchCostEntry.objects.create(
        batch=b, category=BatchCostEntry.Category.FEED,
        amount_uzs=Decimal("1000000"), description="корм неделя 2",
        occurred_at=timezone.now() - timedelta(days=3), module=m_feedlot,
    )
    return b


def test_trace_returns_full_payload(client, batch):
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    assert resp.status_code == 200, resp.content
    body = resp.json()

    for k in ["batch", "parent", "children", "chain_steps",
              "cost_breakdown", "totals"]:
        assert k in body


def test_trace_includes_parent(client, batch, parent_batch):
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    body = resp.json()
    assert body["parent"] is not None
    assert body["parent"]["doc_number"] == parent_batch.doc_number


def test_trace_aggregates_cost_by_category(client, batch):
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    body = resp.json()
    breakdown = {row["category"]: row for row in body["cost_breakdown"]}

    # 2 записи FEED по 1.5M + 1M = 2.5M
    assert breakdown["feed"]["amount_uzs"] == "2500000.00"
    # 1 запись VET = 0.5M
    assert breakdown["vet"]["amount_uzs"] == "500000.00"

    # Итог 3M
    assert body["totals"]["total_cost_uzs"] == "3000000.00"


def test_trace_share_percent_sums_to_100(client, batch):
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    body = resp.json()
    total_share = sum(
        float(row["share_percent"]) for row in body["cost_breakdown"]
    )
    assert abs(total_share - 100.0) < 0.1


def test_trace_unit_cost(client, batch):
    """3M / 1000 = 3000 UZS за голову (по initial_quantity)."""
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    body = resp.json()
    assert body["totals"]["unit_cost_uzs"] == "3000.00"


def test_trace_includes_chain_steps(client, batch):
    resp = client.get(f"/api/batches/{batch.id}/trace/")
    body = resp.json()
    assert len(body["chain_steps"]) == 1
    assert body["chain_steps"][0]["sequence"] == 1


def test_trace_parent_has_children_when_present(client, parent_batch, batch):
    """parent_batch не имеет своего parent, но виден child (наш batch)."""
    resp = client.get(f"/api/batches/{parent_batch.id}/trace/")
    body = resp.json()
    assert body["parent"] is None
    child_doc_numbers = [c["doc_number"] for c in body["children"]]
    assert batch.doc_number in child_doc_numbers


def test_trace_orphan_batch_has_no_parent_no_children(client, parent_batch):
    """parent_batch без сторонних child — children пустой."""
    resp = client.get(f"/api/batches/{parent_batch.id}/trace/")
    body = resp.json()
    assert body["parent"] is None
    assert body["children"] == []
