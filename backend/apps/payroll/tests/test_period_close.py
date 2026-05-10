"""
Тесты PayrollPeriod close: запрет редактирования смен/корректировок.
"""
from datetime import date

import pytest
from django.core.exceptions import ValidationError as DjErr
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    PayrollAdjustment,
    PayrollPeriod,
    WorkShift,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def org_admin(org):
    u = User.objects.create(email="oa-period@t.l", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="A",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="admin"),
        level=AccessLevel.ADMIN,
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def employee(org):
    u = User.objects.create(email="period-emp@t.l", full_name="W", is_active=True)
    return OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_closed_period_blocks_workshift_edit(employee, org):
    PayrollPeriod.objects.create(
        organization=org,
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        status=PayrollPeriod.Status.CLOSED,
    )
    s = WorkShift(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 15), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    with pytest.raises(DjErr):
        s.full_clean()


def test_open_period_allows_workshift(employee, org):
    """Если период открыт — редактирование разрешено."""
    PayrollPeriod.objects.create(
        organization=org,
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        status=PayrollPeriod.Status.OPEN,
    )
    s = WorkShift(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 15), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    s.full_clean()  # без exception


def test_closed_period_blocks_adjustment(employee, org):
    PayrollPeriod.objects.create(
        organization=org,
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        status=PayrollPeriod.Status.CLOSED,
    )
    adj = PayrollAdjustment(
        organization=org, employee=employee,
        kind=PayrollAdjustment.Kind.BONUS,
        effective_date=date(2026, 4, 15),
        amount_uzs=10000,
    )
    with pytest.raises(DjErr):
        adj.full_clean()


def test_close_and_reopen_via_api(org_admin, org):
    api = _client(org_admin)
    r = api.post("/api/payroll/periods/", {
        "period_from": "2026-05-01",
        "period_to": "2026-05-31",
        "status": "open",
    }, format="json")
    assert r.status_code == 201, r.content
    pid = r.json()["id"]

    r = api.post(f"/api/payroll/periods/{pid}/close/")
    assert r.status_code == 200
    assert r.json()["status"] == "closed"

    r = api.post(f"/api/payroll/periods/{pid}/reopen/")
    assert r.status_code == 200
    assert r.json()["status"] == "open"


def test_only_admin_can_reopen(employee, org):
    """hr:rw без admin override НЕ может reopen."""
    period = PayrollPeriod.objects.create(
        organization=org,
        period_from=date(2026, 5, 1), period_to=date(2026, 5, 31),
        status=PayrollPeriod.Status.CLOSED,
    )
    u = User.objects.create(email="hr-only-rw@t.l", full_name="N", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="N",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.WRITE if hasattr(AccessLevel, "WRITE") else AccessLevel.READ_WRITE,
    )
    api = _client(u)
    r = api.post(f"/api/payroll/periods/{period.id}/reopen/")
    assert r.status_code == 400
