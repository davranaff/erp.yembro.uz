"""
Тесты /api/users/me/favorites/ — закреплённые страницы.
"""
import pytest
from rest_framework.test import APIClient

from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User, UserFavoritePage


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user_a(org):
    u = User.objects.create(email="alice@y.local", full_name="Alice")
    u.set_password("x")
    u.save()
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    return u


@pytest.fixture
def user_b(org):
    u = User.objects.create(email="bob@y.local", full_name="Bob")
    u.set_password("x")
    u.save()
    OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    return u


@pytest.fixture
def client_a(user_a):
    api = APIClient()
    api.force_authenticate(user=user_a)
    return api


@pytest.fixture
def client_b(user_b):
    api = APIClient()
    api.force_authenticate(user=user_b)
    return api


def test_no_org_header_required(client_a):
    """Endpoint per-user, X-Organization-Code не нужен."""
    resp = client_a.get("/api/users/me/favorites/")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_then_list(client_a, user_a):
    resp = client_a.post(
        "/api/users/me/favorites/",
        {"href": "/sales", "label": "Продажи"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["href"] == "/sales"
    assert body["label"] == "Продажи"
    assert "id" in body

    resp = client_a.get("/api/users/me/favorites/")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["href"] == "/sales"


def test_list_only_my_favorites(client_a, client_b, user_a, user_b):
    UserFavoritePage.objects.create(user=user_a, href="/sales", label="Продажи A")
    UserFavoritePage.objects.create(user=user_b, href="/purchases", label="Закупки B")

    resp = client_a.get("/api/users/me/favorites/")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["href"] == "/sales"

    resp = client_b.get("/api/users/me/favorites/")
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["href"] == "/purchases"


def test_unique_per_user_per_href(client_a, user_a):
    UserFavoritePage.objects.create(user=user_a, href="/sales", label="Продажи")
    resp = client_a.post(
        "/api/users/me/favorites/",
        {"href": "/sales", "label": "Опять"},
        format="json",
    )
    assert resp.status_code == 400
    assert "href" in resp.json()


def test_delete(client_a, user_a):
    fav = UserFavoritePage.objects.create(user=user_a, href="/sales", label="Продажи")
    resp = client_a.delete(f"/api/users/me/favorites/{fav.id}/")
    assert resp.status_code == 204
    assert not UserFavoritePage.objects.filter(pk=fav.id).exists()


def test_cannot_delete_others_favorite(client_a, user_b):
    """Пользователь не должен видеть/удалять чужое."""
    fav = UserFavoritePage.objects.create(
        user=user_b, href="/sales", label="Продажи Bob"
    )
    resp = client_a.delete(f"/api/users/me/favorites/{fav.id}/")
    assert resp.status_code == 404
    # Не удалилось
    assert UserFavoritePage.objects.filter(pk=fav.id).exists()


def test_validate_href_must_start_with_slash(client_a):
    resp = client_a.post(
        "/api/users/me/favorites/",
        {"href": "sales", "label": "Продажи"},
        format="json",
    )
    assert resp.status_code == 400
    assert "href" in resp.json()


def test_unauthenticated_rejected():
    api = APIClient()
    resp = api.get("/api/users/me/favorites/")
    assert resp.status_code == 401
