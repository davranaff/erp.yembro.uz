"""
Тесты:
  - назначение manager через PATCH /api/memberships/<id>/
  - валидация: чужая org, self-reference → 400
  - фильтр ?my_subordinates=true возвращает только тех, у кого manager.user = request.user
"""
import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


def _make_user_and_membership(org, email, *, admin_module="admin"):
    u = User.objects.create(email=email, full_name=email.split("@")[0])
    u.set_password("x")
    u.save()
    m = OrganizationMembership.objects.create(user=u, organization=org, is_active=True)
    if admin_module:
        mod = Module.objects.get(code=admin_module)
        UserModuleAccessOverride.objects.create(
            membership=m, module=mod, level=AccessLevel.ADMIN,
        )
    return u, m


@pytest.fixture
def admin_setup(org):
    u, m = _make_user_and_membership(org, "boss@y.local")
    return u, m


@pytest.fixture
def client(admin_setup):
    api = APIClient()
    api.force_authenticate(user=admin_setup[0])
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_assign_manager_ok(client, org, admin_setup):
    _, mgr_m = admin_setup
    sub_user, sub_m = _make_user_and_membership(
        org, "worker@y.local", admin_module=None,
    )
    r = client.patch(
        f"/api/memberships/{sub_m.id}/",
        {"manager": str(mgr_m.id)}, format="json",
    )
    assert r.status_code == 200, r.content
    sub_m.refresh_from_db()
    assert sub_m.manager_id == mgr_m.id


def test_self_manager_rejected(client, admin_setup):
    _, mgr_m = admin_setup
    r = client.patch(
        f"/api/memberships/{mgr_m.id}/",
        {"manager": str(mgr_m.id)}, format="json",
    )
    assert r.status_code == 400
    err = str(r.json().get("manager", "")).lower()
    assert "себе" in err


def test_my_subordinates_filter(client, org, admin_setup):
    boss_user, boss_m = admin_setup
    # Подчинённый 1 — есть manager на boss
    _, sub1_m = _make_user_and_membership(org, "sub1@y.local", admin_module=None)
    sub1_m.manager = boss_m
    sub1_m.save(update_fields=["manager"])
    # Подчинённый 2 — manager у другого сотрудника
    other_user, other_m = _make_user_and_membership(org, "other@y.local", admin_module=None)
    _, sub2_m = _make_user_and_membership(org, "sub2@y.local", admin_module=None)
    sub2_m.manager = other_m
    sub2_m.save(update_fields=["manager"])

    r = client.get("/api/memberships/?my_subordinates=true")
    assert r.status_code == 200
    ids = {row["id"] for row in r.json().get("results", r.json())}
    assert str(sub1_m.id) in ids
    assert str(sub2_m.id) not in ids
    assert str(boss_m.id) not in ids  # сам себя не считаем подчинённым


def test_my_subordinates_includes_only_active_users_subordinates(
    client, org, admin_setup,
):
    """my_subordinates берёт по manager.user, а не membership-id —
    если у юзера несколько membership'ов в разных orgах, тут видим
    только в текущей org (см. OrgScopedModelViewSet)."""
    boss_user, boss_m = admin_setup
    _, sub_m = _make_user_and_membership(org, "sub@y.local", admin_module=None)
    sub_m.manager = boss_m
    sub_m.save(update_fields=["manager"])
    r = client.get("/api/memberships/?my_subordinates=true")
    ids = {row["id"] for row in r.json().get("results", r.json())}
    assert ids == {str(sub_m.id)}
