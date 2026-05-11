"""
Тест auto-detect OVERTIME.
"""
from datetime import date
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import WorkSchedule, WorkScheduleTemplate, WorkShift
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="ot-admin@t.l", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="HR",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def employee_with_template(org):
    u = User.objects.create(email="ot-emp@t.l", full_name="W", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    tpl = WorkScheduleTemplate.objects.create(
        organization=org, code="OT-TST",
        name="Стандарт 9-18 (8ч)",
        pattern_kind="weekday_mask",
        pattern={
            "weekdays": [0, 1, 2, 3, 4],
            "start": "09:00", "end": "18:00",
            "duration_hours": 8,
        },
    )
    WorkSchedule.objects.create(
        organization=org, employee=m, template=tpl,
        effective_from=date(2026, 1, 1),
    )
    return m


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_overtime_auto_detected_when_hours_exceed(hr_admin, employee_with_template):
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/", {
        "employee": str(employee_with_template.id),
        "shift_date": "2026-06-01",
        "kind": "work",
        "hours": "10",  # 10 > 8 (норма)
    }, format="json")
    assert r.status_code == 201, r.content
    s = WorkShift.objects.get(pk=r.json()["id"])
    assert s.kind == WorkShift.Kind.OVERTIME


def test_normal_hours_not_overtime(hr_admin, employee_with_template):
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/", {
        "employee": str(employee_with_template.id),
        "shift_date": "2026-06-02",
        "kind": "work",
        "hours": "8",
    }, format="json")
    assert r.status_code == 201
    s = WorkShift.objects.get(pk=r.json()["id"])
    assert s.kind == WorkShift.Kind.WORK


def test_no_template_no_auto_detect(hr_admin, org):
    """Сотрудник без шаблона — overtime не определяется."""
    u = User.objects.create(email="no-tpl@t.l", full_name="N", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/", {
        "employee": str(m.id),
        "shift_date": "2026-06-01",
        "kind": "work",
        "hours": "12",
    }, format="json")
    assert r.status_code == 201
    s = WorkShift.objects.get(pk=r.json()["id"])
    assert s.kind == WorkShift.Kind.WORK
