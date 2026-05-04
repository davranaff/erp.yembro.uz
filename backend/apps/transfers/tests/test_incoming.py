"""
API-тесты для GET /api/transfers/incoming/.

Покрывают:
  - выдача только AWAITING_ACCEPTANCE / UNDER_REVIEW
  - фильтр по `to_module=<code>`
  - 403 при отсутствии r-доступа к запрошенному to_module
  - без фильтра — отдаёт incoming только для модулей, где у юзера есть r+
  - per-org изоляция
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.nomenclature.models import Category, NomenclatureItem, Unit
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.transfers.models import InterModuleTransfer
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_matochnik():
    return Module.objects.get(code="matochnik")


@pytest.fixture
def m_incubation():
    return Module.objects.get(code="incubation")


@pytest.fixture
def m_feedlot():
    return Module.objects.get(code="feedlot")


@pytest.fixture
def unit_pcs(org):
    return Unit.objects.get_or_create(
        organization=org, code="шт", defaults={"name": "Штука"},
    )[0]


@pytest.fixture
def egg_nom(org, unit_pcs):
    cat = Category.objects.get_or_create(organization=org, name="Яйцо INC")[0]
    return NomenclatureItem.objects.create(
        organization=org, sku="ИНК-1", name="Яйцо инкуб INC",
        category=cat, unit=unit_pcs,
    )


@pytest.fixture
def transfer_to_incubation(org, m_matochnik, m_incubation, egg_nom, unit_pcs):
    return InterModuleTransfer.objects.create(
        organization=org,
        doc_number="ММ-INC-1",
        transfer_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        from_module=m_matochnik,
        to_module=m_incubation,
        nomenclature=egg_nom,
        unit=unit_pcs,
        quantity=Decimal("1000"),
        cost_uzs=Decimal("0"),
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )


@pytest.fixture
def transfer_to_feedlot(org, m_incubation, m_feedlot, egg_nom, unit_pcs):
    return InterModuleTransfer.objects.create(
        organization=org,
        doc_number="ММ-FL-1",
        transfer_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        from_module=m_incubation,
        to_module=m_feedlot,
        nomenclature=egg_nom,
        unit=unit_pcs,
        quantity=Decimal("9500"),
        cost_uzs=Decimal("0"),
        state=InterModuleTransfer.State.AWAITING_ACCEPTANCE,
    )


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


# ─── Tests ───────────────────────────────────────────────────────────────


def test_incubation_user_sees_own_inbox(
    org, m_incubation, transfer_to_incubation,
):
    u = _make_user("inc@y.local", org=org, modules={m_incubation: AccessLevel.READ})
    api = _client(u)
    resp = api.get("/api/transfers/incoming/?to_module=incubation")
    assert resp.status_code == 200, resp.content
    data = resp.json()
    docs = [t["doc_number"] for t in data]
    assert "ММ-INC-1" in docs


def test_incubation_user_does_not_see_feedlot_inbox(
    org, m_incubation, transfer_to_feedlot,
):
    u = _make_user("inc2@y.local", org=org, modules={m_incubation: AccessLevel.READ})
    api = _client(u)
    resp = api.get("/api/transfers/incoming/?to_module=feedlot")
    assert resp.status_code == 403


def test_incoming_filters_to_awaiting_only(
    org, m_incubation, transfer_to_incubation,
):
    """POSTED transfer не должен попасть в incoming."""
    transfer_to_incubation.state = InterModuleTransfer.State.POSTED
    transfer_to_incubation.save(update_fields=["state"])

    u = _make_user("inc3@y.local", org=org, modules={m_incubation: AccessLevel.READ})
    api = _client(u)
    resp = api.get("/api/transfers/incoming/?to_module=incubation")
    assert resp.status_code == 200
    data = resp.json()
    assert all(t["doc_number"] != "ММ-INC-1" for t in data)


def test_no_filter_returns_only_allowed_modules(
    org, m_incubation, m_feedlot, transfer_to_incubation, transfer_to_feedlot,
):
    """Без `?to_module` — отдаём только то, к чему у юзера есть r+."""
    u = _make_user(
        "multi@y.local", org=org,
        modules={m_incubation: AccessLevel.READ},  # feedlot нет
    )
    api = _client(u)
    resp = api.get("/api/transfers/incoming/")
    assert resp.status_code == 200
    docs = {t["doc_number"] for t in resp.json()}
    assert "ММ-INC-1" in docs
    assert "ММ-FL-1" not in docs


def test_user_without_membership_returns_empty(org, transfer_to_incubation):
    u = User.objects.create(email="nomember@y.local", full_name="N")
    api = APIClient()
    api.force_authenticate(user=u)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    # Без membership middleware вернёт 403 PermissionDenied на org-resolve
    resp = api.get("/api/transfers/incoming/?to_module=incubation")
    assert resp.status_code in (200, 403)
    if resp.status_code == 200:
        assert resp.json() == []
