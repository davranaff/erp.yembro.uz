"""
Smoke-тесты AuditMixin: CRUD через API → запись в AuditLog.

Используем CounterpartyViewSet как самый простой CRUD (есть organization).
"""
import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.counterparties.models import Counterparty
from apps.organizations.models import Organization, OrganizationMembership
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def user(org):
    from apps.modules.models import Module
    from apps.rbac.models import AccessLevel, UserModuleAccessOverride

    u = User.objects.create(email="audit@y.local", full_name="Auditor")
    u.set_password("x")
    u.save()
    membership = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True,
    )
    # Даём admin-доступ на модуль "core" (Counterparty CRUD)
    core_mod = Module.objects.get(code="core")
    UserModuleAccessOverride.objects.create(
        membership=membership, module=core_mod, level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def _count_for(model_cls, action):
    from django.contrib.contenttypes.models import ContentType
    ct = ContentType.objects.get_for_model(model_cls)
    return AuditLog.objects.filter(
        entity_content_type=ct, action=action
    ).count()


def test_create_writes_audit(client, user, org):
    before = _count_for(Counterparty, AuditLog.Action.CREATE)
    resp = client.post(
        "/api/counterparties/",
        {"code": "К-A-01", "kind": "supplier", "name": "Контрагент А"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    after = _count_for(Counterparty, AuditLog.Action.CREATE)
    assert after == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.CREATE,
        actor=user,
        organization=org,
    ).order_by("-occurred_at").first()
    assert log is not None
    assert "Контрагент А" in log.entity_repr


def test_update_writes_audit(client):
    cp = Counterparty.objects.create(
        organization=Organization.objects.get(code="DEFAULT"),
        code="К-B-01", kind="supplier", name="Старое имя",
    )
    before = _count_for(Counterparty, AuditLog.Action.UPDATE)
    resp = client.patch(
        f"/api/counterparties/{cp.id}/",
        {"name": "Новое имя"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    after = _count_for(Counterparty, AuditLog.Action.UPDATE)
    assert after == before + 1


def test_delete_writes_audit_with_entity_repr(client):
    cp = Counterparty.objects.create(
        organization=Organization.objects.get(code="DEFAULT"),
        code="К-C-01", kind="supplier", name="Удаляемый",
    )
    before = _count_for(Counterparty, AuditLog.Action.DELETE)
    resp = client.delete(f"/api/counterparties/{cp.id}/")
    assert resp.status_code == 204, resp.content
    after = _count_for(Counterparty, AuditLog.Action.DELETE)
    assert after == before + 1

    log = AuditLog.objects.filter(
        action=AuditLog.Action.DELETE,
    ).order_by("-occurred_at").first()
    # entity_repr снапшотится — даже после delete виден "Удаляемый"
    assert "Удаляемый" in log.entity_repr


def test_audit_captures_ip_and_user_agent(client):
    client.credentials(
        HTTP_X_ORGANIZATION_CODE="DEFAULT",
        HTTP_USER_AGENT="TestAgent/1.0",
        REMOTE_ADDR="10.0.0.1",
    )
    resp = client.post(
        "/api/counterparties/",
        {"code": "К-D-01", "kind": "buyer", "name": "Buyer D"},
        format="json",
    )
    assert resp.status_code == 201
    log = AuditLog.objects.filter(action=AuditLog.Action.CREATE).order_by("-occurred_at").first()
    assert log.user_agent == "TestAgent/1.0"
    assert str(log.ip_address) == "10.0.0.1"
