"""
Тесты audit-trail на изменения прав.

Требование: каждое CRUD-изменение RolePermission, UserRole,
UserModuleAccessOverride пишет ровно одну запись в AuditLog
с action=PERMISSION_CHANGE.
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.rbac.models import (
    AccessLevel,
    Role,
    RolePermission,
    UserModuleAccessOverride,
    UserRole,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def admin_user(org):
    u = User.objects.create(email="rbac-tester@y.local", full_name="RBAC Tester")
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    admin_mod = Module.objects.get(code="admin")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=admin_mod, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(admin_user):
    api = APIClient()
    api.force_authenticate(user=admin_user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def _count_perm_changes():
    return AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).count()


def test_create_role_permission_writes_audit(client, org):
    role = Role.objects.create(organization=org, code="t1", name="Test")
    feedlot = Module.objects.get(code="feedlot")

    before = _count_perm_changes()
    resp = client.post(
        "/api/rbac/role-permissions/",
        {"role": str(role.id), "module": str(feedlot.id), "level": "rw"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "feedlot" in log.action_verb
    assert "rw" in log.action_verb
    # entity = role (по нашему контракту)
    assert log.entity_repr == str(role)


def test_update_role_permission_writes_audit_with_old_new(client, org):
    role = Role.objects.create(organization=org, code="t2", name="Test 2")
    feedlot = Module.objects.get(code="feedlot")
    rp = RolePermission.objects.create(role=role, module=feedlot, level=AccessLevel.READ)

    before = _count_perm_changes()
    resp = client.patch(
        f"/api/rbac/role-permissions/{rp.id}/",
        {"level": "admin"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "feedlot" in log.action_verb
    assert "r→admin" in log.action_verb


def test_update_no_op_does_not_write_audit(client, org):
    """PATCH без изменения level → не пишем audit (избегаем шума)."""
    role = Role.objects.create(organization=org, code="t3", name="Test 3")
    feedlot = Module.objects.get(code="feedlot")
    rp = RolePermission.objects.create(role=role, module=feedlot, level=AccessLevel.READ)

    before = _count_perm_changes()
    resp = client.patch(
        f"/api/rbac/role-permissions/{rp.id}/",
        {"level": "r"},
        format="json",
    )
    assert resp.status_code == 200
    assert _count_perm_changes() == before


def test_delete_role_permission_writes_revoked(client, org):
    role = Role.objects.create(organization=org, code="t4", name="Test 4")
    feedlot = Module.objects.get(code="feedlot")
    rp = RolePermission.objects.create(role=role, module=feedlot, level=AccessLevel.READ)

    before = _count_perm_changes()
    resp = client.delete(f"/api/rbac/role-permissions/{rp.id}/")
    assert resp.status_code == 204, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "revoked" in log.action_verb


def test_assign_user_role_writes_audit(client, org, admin_user):
    role = Role.objects.create(organization=org, code="t5", name="Test 5")
    target = User.objects.create(email="target@y.local", full_name="Target")
    membership = OrganizationMembership.objects.create(
        user=target, organization=org, is_active=True
    )

    before = _count_perm_changes()
    resp = client.post(
        "/api/rbac/user-roles/",
        {"membership": str(membership.id), "role": str(role.id)},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "assigned" in log.action_verb
    assert "target@y.local" in log.action_verb


def test_revoke_user_role_writes_audit(client, org):
    role = Role.objects.create(organization=org, code="t6", name="Test 6")
    target = User.objects.create(email="target2@y.local", full_name="Target 2")
    membership = OrganizationMembership.objects.create(
        user=target, organization=org, is_active=True
    )
    ur = UserRole.objects.create(membership=membership, role=role)

    before = _count_perm_changes()
    resp = client.delete(f"/api/rbac/user-roles/{ur.id}/")
    assert resp.status_code == 204, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "revoked" in log.action_verb


def test_create_override_writes_audit(client, org):
    target = User.objects.create(email="ovrd@y.local", full_name="Ovrd")
    membership = OrganizationMembership.objects.create(
        user=target, organization=org, is_active=True
    )
    feedlot = Module.objects.get(code="feedlot")

    before = _count_perm_changes()
    resp = client.post(
        "/api/rbac/overrides/",
        {
            "membership": str(membership.id),
            "module": str(feedlot.id),
            "level": "admin",
            "reason": "интерим-замена",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert _count_perm_changes() == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.PERMISSION_CHANGE
    ).order_by("-occurred_at").first()
    assert "override" in log.action_verb
    assert "feedlot" in log.action_verb
    assert "admin" in log.action_verb
    assert "ovrd@y.local" in log.action_verb
