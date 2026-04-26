"""
Тесты диапазона дат + actor/entity фильтров на /api/audit/.
"""
from datetime import datetime, timedelta, timezone

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def admin_user(org):
    from apps.modules.models import Module
    from apps.rbac.models import AccessLevel, UserModuleAccessOverride

    u = User.objects.create(email="audit-filter@y.local", full_name="Audit Tester")
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


def _make_log(*, organization, actor, when, action=AuditLog.Action.CREATE):
    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action,
        action_verb="test",
        entity_repr="Sample",
        occurred_at=when,
    )


def test_date_after_filter(client, org, admin_user):
    base = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    _make_log(organization=org, actor=admin_user, when=base)
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=10))
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=20))

    resp = client.get("/api/audit/?date_after=2026-04-15T00:00:00Z")
    assert resp.status_code == 200, resp.content
    results = resp.json().get("results", resp.json())
    assert len(results) == 1


def test_date_range_filter(client, org, admin_user):
    base = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    _make_log(organization=org, actor=admin_user, when=base)
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=5))
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=10))
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=20))

    resp = client.get(
        "/api/audit/"
        "?date_after=2026-04-04T00:00:00Z"
        "&date_before=2026-04-15T00:00:00Z"
    )
    assert resp.status_code == 200
    results = resp.json().get("results", resp.json())
    assert len(results) == 2


def test_actor_filter(client, org, admin_user):
    other = User.objects.create(email="other@y.local", full_name="Other")
    base = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    _make_log(organization=org, actor=admin_user, when=base)
    _make_log(organization=org, actor=other, when=base + timedelta(hours=1))

    resp = client.get(f"/api/audit/?actor={admin_user.id}")
    assert resp.status_code == 200
    results = resp.json().get("results", resp.json())
    assert len(results) == 1
    assert results[0]["actor"] == str(admin_user.id)


def test_csv_export_streams_with_filter(client, org, admin_user):
    base = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    _make_log(organization=org, actor=admin_user, when=base)
    _make_log(organization=org, actor=admin_user, when=base + timedelta(days=20))

    resp = client.get(
        "/api/audit/export/?date_after=2026-04-15T00:00:00Z"
    )
    assert resp.status_code == 200
    assert "text/csv" in resp["Content-Type"]
    body = b"".join(resp.streaming_content).decode("utf-8")
    # BOM + заголовок + 1 строка
    assert "occurred_at" in body
    assert body.count("\n") >= 2  # header + at least one row
    # вторая запись (ранняя) не должна попасть
    assert body.count("Sample") == 1
