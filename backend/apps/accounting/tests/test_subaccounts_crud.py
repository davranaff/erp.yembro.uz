"""
Тесты CRUD GLSubaccount через API.

Сценарии:
    1. Admin может создать субсчёт.
    2. Нельзя создать с дублирующим code в рамках account.
    3. Admin может обновить name.
    4. Admin может удалить неиспользуемый субсчёт.
    5. Нельзя удалить субсчёт с PROTECT-ссылками.
"""
import pytest
from rest_framework.test import APIClient

from apps.accounting.models import GLAccount, GLSubaccount
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def admin_user(org):
    u = User.objects.create(email="sub-admin@y.local", full_name="Admin")
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    ledger = Module.objects.get(code="ledger")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=ledger, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_admin_can_create_subaccount(client, org):
    """POST /api/accounting/subaccounts/ → создаётся субсчёт."""
    parent = GLAccount.objects.get(organization=org, code="26")
    resp = client.post(
        "/api/accounting/subaccounts/",
        {
            "account": str(parent.id),
            "code": "26.10",
            "name": "Ремонт оборудования",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert GLSubaccount.objects.filter(account=parent, code="26.10").exists()


def test_duplicate_code_raises_400(client, org):
    parent = GLAccount.objects.get(organization=org, code="26")
    GLSubaccount.objects.create(account=parent, code="26.99", name="first")
    resp = client.post(
        "/api/accounting/subaccounts/",
        {
            "account": str(parent.id),
            "code": "26.99",
            "name": "duplicate",
        },
        format="json",
    )
    assert resp.status_code == 400, resp.content


def test_admin_can_update_name(client, org):
    parent = GLAccount.objects.get(organization=org, code="26")
    sub = GLSubaccount.objects.create(
        account=parent, code="26.20", name="Старое",
    )
    resp = client.patch(
        f"/api/accounting/subaccounts/{sub.id}/",
        {"name": "Новое"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    sub.refresh_from_db()
    assert sub.name == "Новое"


def test_admin_can_delete_unused_subaccount(client, org):
    parent = GLAccount.objects.get(organization=org, code="26")
    sub = GLSubaccount.objects.create(
        account=parent, code="26.21", name="Временный",
    )
    resp = client.delete(f"/api/accounting/subaccounts/{sub.id}/")
    assert resp.status_code == 204, resp.content
    assert not GLSubaccount.objects.filter(pk=sub.pk).exists()


def test_cannot_create_subaccount_without_admin_level(org):
    """Пользователь с уровнем rw (не admin) на ledger не может создавать."""
    u = User.objects.create(email="ledger-rw@y.local", full_name="RW")
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    ledger = Module.objects.get(code="ledger")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=ledger, level=AccessLevel.READ_WRITE,
    )

    api = APIClient()
    api.force_authenticate(user=u)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")

    parent = GLAccount.objects.get(organization=org, code="26")
    resp = api.post(
        "/api/accounting/subaccounts/",
        {
            "account": str(parent.id),
            "code": "26.30",
            "name": "Проба",
        },
        format="json",
    )
    assert resp.status_code == 403, resp.content
