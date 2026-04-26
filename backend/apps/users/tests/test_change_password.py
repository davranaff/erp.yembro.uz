"""
Тесты POST /api/users/me/change-password/.
"""
import pytest
from rest_framework.test import APIClient

from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def user():
    u = User.objects.create(email="cp@y.local", full_name="CP User")
    u.set_password("OldPass2026!")
    u.save()
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    return api


def test_change_password_ok(client, user):
    resp = client.post(
        "/api/users/me/change-password/",
        {"old_password": "OldPass2026!", "new_password": "NewSecret9876"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    user.refresh_from_db()
    assert user.check_password("NewSecret9876")
    assert not user.check_password("OldPass2026!")


def test_change_password_wrong_old(client, user):
    resp = client.post(
        "/api/users/me/change-password/",
        {"old_password": "wrong", "new_password": "NewSecret9876"},
        format="json",
    )
    assert resp.status_code == 400
    assert "old_password" in resp.json()
    user.refresh_from_db()
    assert user.check_password("OldPass2026!")  # пароль не сменился


def test_change_password_too_short(client, user):
    resp = client.post(
        "/api/users/me/change-password/",
        {"old_password": "OldPass2026!", "new_password": "short"},
        format="json",
    )
    assert resp.status_code == 400
    assert "new_password" in resp.json()


def test_change_password_same_as_old(client, user):
    resp = client.post(
        "/api/users/me/change-password/",
        {"old_password": "OldPass2026!", "new_password": "OldPass2026!"},
        format="json",
    )
    assert resp.status_code == 400
    assert "new_password" in resp.json()


def test_change_password_unauthenticated_rejected():
    api = APIClient()
    resp = api.post(
        "/api/users/me/change-password/",
        {"old_password": "x", "new_password": "y"},
        format="json",
    )
    assert resp.status_code == 401


def test_change_password_missing_fields(client):
    resp = client.post("/api/users/me/change-password/", {}, format="json")
    assert resp.status_code == 400
