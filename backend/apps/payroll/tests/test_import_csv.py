"""
Тест импорта табеля из CSV.
"""
from datetime import date

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
    u = User.objects.create(email="csv-admin@t.l", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="HR",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


@pytest.fixture
def alice(org):
    u = User.objects.create(email="alice@t.l", full_name="Alice", is_active=True)
    return OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )


@pytest.fixture
def bob(org):
    u = User.objects.create(email="bob@t.l", full_name="Bob", is_active=True)
    return OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def test_import_csv_creates_shifts(hr_admin, alice, bob):
    csv_text = (
        "email,date,kind,hours,notes\n"
        "alice@t.l,2026-06-01,work,8,\n"
        "alice@t.l,2026-06-02,vacation,,Отпуск\n"
        "bob@t.l,2026-06-01,work,8,\n"
    )
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/import-csv/", {
        "csv_text": csv_text,
    }, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["created"] == 3
    assert body["errors"] == 0
    assert WorkShift.objects.filter(employee=alice).count() == 2
    s = WorkShift.objects.get(employee=alice, shift_date=date(2026, 6, 2))
    assert s.kind == WorkShift.Kind.VACATION
    assert s.notes == "Отпуск"
    assert s.source == WorkShift.Source.IMPORT


def test_import_csv_collects_errors(hr_admin, alice):
    csv_text = (
        "email,date,kind,hours,notes\n"
        "unknown@t.l,2026-06-01,work,8,\n"
        "alice@t.l,bad-date,work,8,\n"
        "alice@t.l,2026-06-01,bogus_kind,8,\n"
    )
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/import-csv/", {
        "csv_text": csv_text,
    }, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["created"] == 0
    assert body["errors"] == 3
    assert len(body["error_lines"]) == 3


def test_import_csv_skip_existing(hr_admin, alice, org):
    WorkShift.objects.create(
        organization=org, employee=alice,
        shift_date=date(2026, 6, 1), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    csv_text = "email,date,kind,hours,notes\nalice@t.l,2026-06-01,vacation,,\n"
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/import-csv/", {
        "csv_text": csv_text,
        "skip_existing": True,
    }, format="json")
    assert r.status_code == 200
    s = WorkShift.objects.get(employee=alice, shift_date=date(2026, 6, 1))
    assert s.kind == WorkShift.Kind.WORK  # не перезаписалось


def test_import_csv_overwrite_existing(hr_admin, alice, org):
    WorkShift.objects.create(
        organization=org, employee=alice,
        shift_date=date(2026, 6, 1), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    csv_text = "email,date,kind,hours,notes\nalice@t.l,2026-06-01,vacation,,\n"
    api = _client(hr_admin)
    r = api.post("/api/payroll/work-shifts/import-csv/", {
        "csv_text": csv_text,
        "skip_existing": False,
    }, format="json")
    assert r.status_code == 200
    s = WorkShift.objects.get(employee=alice, shift_date=date(2026, 6, 1))
    assert s.kind == WorkShift.Kind.VACATION
    assert s.source == WorkShift.Source.IMPORT
