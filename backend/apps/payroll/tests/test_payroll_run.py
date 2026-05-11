"""
Тесты PayrollRun: preview + execute.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounting.models import GLSubaccount
from apps.currency.models import Currency
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payments.models import Payment
from apps.payroll.models import (
    CompensationPlan,
    PayrollPayout,
    PayrollRun,
    SalaryRate,
    WorkShift,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def cash(org):
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="run-admin@t.l", full_name="A", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="HR",
    )
    UserModuleAccessOverride.objects.create(
        membership=m, module=Module.objects.get(code="hr"),
        level=AccessLevel.ADMIN,
    )
    return u


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


def _make_emp(org, uzs, email, *, rate=Decimal("100000"), shifts=1):
    u = User.objects.create(email=email, full_name=email.split("@")[0], is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="W",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=CompensationPlan.Type.PER_SHIFT,
        currency=uzs,
    )
    SalaryRate.objects.create(
        organization=org, employee=m,
        amount=rate, currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    for i in range(shifts):
        WorkShift.objects.create(
            organization=org, employee=m,
            shift_date=date(2026, 4, 5 + i),
            kind=WorkShift.Kind.WORK,
            source=WorkShift.Source.MANUAL,
        )
    return m


def test_preview_returns_employees_with_positive_balance(hr_admin, org, uzs):
    e1 = _make_emp(org, uzs, "p1@t.l", rate=Decimal("100000"), shifts=2)  # bal 200k
    e2 = _make_emp(org, uzs, "p2@t.l", shifts=0)  # bal 0
    api = _client(hr_admin)
    r = api.post("/api/payroll/runs/preview/", {
        "period_from": "2026-04-01",
        "period_to": "2026-04-30",
    }, format="json")
    assert r.status_code == 200, r.content
    body = r.json()
    ids = [row["employee_id"] for row in body["rows"]]
    assert str(e1.id) in ids
    assert str(e2.id) not in ids
    assert Decimal(body["total_uzs"]) >= Decimal("200000")


def test_execute_creates_payouts_and_run(hr_admin, org, uzs, cash):
    e1 = _make_emp(org, uzs, "ex1@t.l", rate=Decimal("100000"), shifts=2)
    e2 = _make_emp(org, uzs, "ex2@t.l", rate=Decimal("100000"), shifts=1)
    api = _client(hr_admin)
    r = api.post("/api/payroll/runs/execute/", {
        "period_from": "2026-04-01",
        "period_to": "2026-04-30",
        "cash_subaccount": str(cash.id),
        "payout_type": "salary",
    }, format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["status"] == "executed"
    assert body["employees_count"] == 2
    assert Decimal(body["total_amount_uzs"]) == Decimal("300000")  # 200k + 100k

    run = PayrollRun.objects.get(pk=body["id"])
    payouts = list(PayrollPayout.objects.filter(run=run))
    assert len(payouts) == 2
    for p in payouts:
        p.payment.refresh_from_db()
        assert p.payment.status == Payment.Status.POSTED


def test_execute_with_custom_amounts(hr_admin, org, uzs, cash):
    e1 = _make_emp(org, uzs, "ca1@t.l", rate=Decimal("100000"), shifts=3)  # bal 300k
    e2 = _make_emp(org, uzs, "ca2@t.l", rate=Decimal("100000"), shifts=2)  # bal 200k
    api = _client(hr_admin)
    r = api.post("/api/payroll/runs/execute/", {
        "period_from": "2026-04-01",
        "period_to": "2026-04-30",
        "cash_subaccount": str(cash.id),
        "payout_type": "advance",
        "employee_amounts": {
            str(e1.id): "150000",
            # e2 не выбран
        },
    }, format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["employees_count"] == 1
    assert Decimal(body["total_amount_uzs"]) == Decimal("150000")
    payouts = PayrollPayout.objects.filter(employee=e2)
    assert payouts.count() == 0


def test_execute_rejects_amount_over_balance(hr_admin, org, uzs, cash):
    e1 = _make_emp(org, uzs, "over@t.l", rate=Decimal("100000"), shifts=1)
    api = _client(hr_admin)
    r = api.post("/api/payroll/runs/execute/", {
        "period_from": "2026-04-01",
        "period_to": "2026-04-30",
        "cash_subaccount": str(cash.id),
        "employee_amounts": {str(e1.id): "200000"},  # больше чем balance 100k
    }, format="json")
    assert r.status_code == 400, r.content


def test_execute_no_employees_to_pay(hr_admin, org, uzs, cash):
    """Все балансы ≤ 0 → 400."""
    api = _client(hr_admin)
    r = api.post("/api/payroll/runs/execute/", {
        "period_from": "2026-04-01",
        "period_to": "2026-04-30",
        "cash_subaccount": str(cash.id),
    }, format="json")
    assert r.status_code == 400, r.content
