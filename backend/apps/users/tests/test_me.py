"""
Тесты GET /api/users/me/ и PATCH /api/users/me/.
"""
import pytest
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user(org):
    u = User.objects.create(email="me@y.local", full_name="Me User", phone="+998 90 000 0000")
    u.set_password("password123")
    u.save()
    OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="Менеджер",
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_me_get_returns_user_with_memberships(client, user, org):
    resp = client.get("/api/users/me/")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["email"] == user.email
    assert body["full_name"] == "Me User"
    assert isinstance(body["memberships"], list)
    assert len(body["memberships"]) == 1
    m = body["memberships"][0]
    assert m["organization"]["code"] == org.code
    assert "module_permissions" in m
    assert isinstance(m["module_permissions"], dict)
    # Поле для org-level toggle модулей: список codes активных модулей.
    assert "enabled_modules" in m
    assert isinstance(m["enabled_modules"], list)


def test_me_enabled_modules_excludes_disabled(client, user, org):
    """OrganizationModule(is_enabled=False) → код пропадает из списка."""
    from apps.modules.models import Module, OrganizationModule

    feed = Module.objects.get(code="feed")
    OrganizationModule.objects.update_or_create(
        organization=org, module=feed, defaults={"is_enabled": False},
    )
    body = client.get("/api/users/me/").json()
    enabled = body["memberships"][0]["enabled_modules"]
    assert "feed" not in enabled


def test_me_enabled_modules_keeps_system_even_if_marked_disabled(client, user, org):
    """admin/ledger/core всегда отдаются как включённые (защита от self-lockout)."""
    from apps.modules.models import Module, OrganizationModule

    admin = Module.objects.get(code="admin")
    OrganizationModule.objects.update_or_create(
        organization=org, module=admin, defaults={"is_enabled": False},
    )
    body = client.get("/api/users/me/").json()
    enabled = body["memberships"][0]["enabled_modules"]
    assert "admin" in enabled


def test_me_get_unauthenticated_rejected():
    api = APIClient()
    resp = api.get("/api/users/me/")
    assert resp.status_code == 401


def test_me_patch_updates_full_name_and_phone(client, user):
    resp = client.patch(
        "/api/users/me/",
        {"full_name": "New Name", "phone": "+998 90 111 2222"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    user.refresh_from_db()
    assert user.full_name == "New Name"
    assert user.phone == "+998 90 111 2222"
    # Возвращается полный MeSerializer
    body = resp.json()
    assert body["full_name"] == "New Name"
    assert "memberships" in body


def test_me_patch_ignores_email_and_is_staff(client, user):
    original_email = user.email
    resp = client.patch(
        "/api/users/me/",
        {"email": "hacker@evil.com", "is_staff": True, "is_superuser": True,
         "full_name": "Whatever"},
        format="json",
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.email == original_email
    assert user.is_staff is False
    assert user.is_superuser is False


def test_me_patch_empty_full_name_rejected(client, user):
    resp = client.patch("/api/users/me/", {"full_name": "   "}, format="json")
    assert resp.status_code == 400


def test_me_put_not_allowed(client):
    resp = client.put("/api/users/me/", {"full_name": "X"}, format="json")
    assert resp.status_code == 405
