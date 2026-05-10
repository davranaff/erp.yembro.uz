"""
Тест bulk-set-kind: массовое назначение kind на даты.
"""
from datetime import date, datetime, timezone

import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import WorkShift
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="bk-admin@t.l", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="HR",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def employee(org):
    u = User.objects.create(email="bk-emp@t.l", full_name="W", is_active=True)
    return OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_bulk_set_kind_creates_new(hr_admin, employee):
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/bulk-set-kind/", {
        "employee": str(employee.id),
        "dates": ["2026-06-01", "2026-06-02", "2026-06-03"],
        "kind": "vacation",
        "notes": "Отпуск",
    }, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["created"] == 3
    assert body["updated"] == 0
    assert WorkShift.objects.filter(
        employee=employee, kind=WorkShift.Kind.VACATION,
    ).count() == 3


def test_bulk_set_kind_updates_existing(hr_admin, employee, org):
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 6, 1), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/bulk-set-kind/", {
        "employee": str(employee.id),
        "dates": ["2026-06-01", "2026-06-02"],
        "kind": "absence",
    }, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["created"] == 1
    assert body["updated"] == 1
    s = WorkShift.objects.get(employee=employee, shift_date=date(2026, 6, 1))
    assert s.kind == WorkShift.Kind.ABSENCE


def test_multi_shift_in_a_day_allowed(hr_admin, employee, org):
    """unique_together теперь по (employee, date, index) — две смены в день можно."""
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 6, 1), shift_index=0,
        kind=WorkShift.Kind.WORK, source=WorkShift.Source.MANUAL,
    )
    # Вторая смена этого же дня (например ночная) — index=1
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 6, 1), shift_index=1,
        kind=WorkShift.Kind.OVERTIME, source=WorkShift.Source.MANUAL,
    )
    assert WorkShift.objects.filter(
        employee=employee, shift_date=date(2026, 6, 1),
    ).count() == 2
