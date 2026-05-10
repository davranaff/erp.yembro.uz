"""
Тесты lifecycle-операций: terminate, cancel payout, edge cases.
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
    SalaryRate,
    WorkSchedule,
    WorkScheduleTemplate,
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
def cash_subaccount(org):
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


def _make_user(org, email, levels):
    """levels: dict module_code -> AccessLevel."""
    u = User.objects.create(email=email, full_name=email.split("@")[0], is_active=True)
    u.set_password("x")
    u.save()
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="T",
    )
    for code, lvl in levels.items():
        UserModuleAccessOverride.objects.create(
            membership=m, module=Module.objects.get(code=code), level=lvl,
        )
    return u, m


@pytest.fixture
def org_admin(org):
    """Юзер с admin-override на несколько модулей (= org-admin по тесту is_org_admin)."""
    u, _ = _make_user(org, "org-admin@test.local", {
        "admin": AccessLevel.ADMIN,
        "hr": AccessLevel.ADMIN,
    })
    return u


@pytest.fixture
def hr_writer(org):
    """hr:rw (без admin) — может писать в payroll, но не считается org_admin."""
    u, _ = _make_user(org, "hr-writer@test.local", {"hr": AccessLevel.READ_WRITE})
    return u


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="emp@test.local", full_name="Emp", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="Worker",
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
    return m


def _client(user):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE="DEFAULT")
    return api


# ─── Terminate ───────────────────────────────────────────────────────────


def test_terminate_closes_rates_and_schedules(
    org_admin, employee, uzs, org,
):
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    tpl = WorkScheduleTemplate.objects.get(organization=org, code="STD-9-18")
    WorkSchedule.objects.create(
        organization=org, employee=employee, template=tpl,
        effective_from=date(2026, 4, 1),
    )

    api = _client(org_admin)
    r = api.post(
        f"/api/memberships/{employee.id}/terminate/",
        {"date": "2026-05-15"}, format="json",
    )
    assert r.status_code == 200, r.content
    employee.refresh_from_db()
    assert not employee.is_active
    assert employee.work_status == "terminated"
    assert SalaryRate.objects.get(employee=employee).effective_to == date(2026, 5, 15)
    assert WorkSchedule.objects.get(employee=employee).effective_to == date(2026, 5, 15)


def test_terminate_returns_balance(
    org_admin, employee, uzs, org, cash_subaccount,
):
    """Эндпоинт возвращает баланс на дату увольнения."""
    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("200000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 15), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    api = _client(org_admin)
    r = api.post(
        f"/api/memberships/{employee.id}/terminate/",
        {"date": "2026-04-30"}, format="json",
    )
    assert r.status_code == 200, r.content
    body = r.json()
    assert Decimal(body["balance_breakdown"]["accrued_total"]) == Decimal("200000")
    assert Decimal(body["balance_at_termination"]) == Decimal("200000")


def test_terminate_requires_org_admin(hr_writer, employee):
    """hr:rw без admin-override НЕ может уволить (только org-admin)."""
    api = _client(hr_writer)
    r = api.post(f"/api/memberships/{employee.id}/terminate/", format="json")
    assert r.status_code == 403, r.content


# ─── Cancel payout ───────────────────────────────────────────────────────


def test_cancel_payout_reverses_payment(
    org_admin, employee, uzs, org, cash_subaccount,
):
    from apps.payroll.services.payout import create_payout

    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    payout = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("100000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash_subaccount,
    )
    assert payout.payment.status == Payment.Status.POSTED

    api = _client(org_admin)
    r = api.post(
        f"/api/payroll/payouts/{payout.id}/cancel/",
        {"reason": "ошибка ввода"}, format="json",
    )
    assert r.status_code == 200, r.content
    payout.payment.refresh_from_db()
    assert payout.payment.status == Payment.Status.CANCELLED
    # PayrollPayout сам не удаляется
    assert PayrollPayout.objects.filter(id=payout.id).exists()


def test_cancel_payout_excludes_from_balance(
    org_admin, employee, uzs, org, cash_subaccount,
):
    from apps.payroll.services.balance import compute_balance
    from apps.payroll.services.payout import create_payout

    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 5), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    payout = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("100000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash_subaccount,
        on_date=date(2026, 4, 30),
    )
    bal = compute_balance(employee, date(2026, 4, 30))
    assert bal.paid_total == Decimal("100000")
    assert bal.balance_uzs == Decimal("0")

    api = _client(org_admin)
    r = api.post(f"/api/payroll/payouts/{payout.id}/cancel/", format="json")
    assert r.status_code == 200

    bal2 = compute_balance(employee, date(2026, 4, 30))
    assert bal2.paid_total == Decimal("0")
    assert bal2.balance_uzs == Decimal("100000")


def test_cancel_payout_requires_org_admin(hr_writer, employee, uzs, org, cash_subaccount):
    """hr:rw (без admin-override) НЕ может cancel — только org_admin."""
    from apps.payroll.services.payout import create_payout

    SalaryRate.objects.create(
        organization=org, employee=employee,
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    payout = create_payout(
        employee=employee,
        type=PayrollPayout.Type.SALARY,
        amount_uzs=Decimal("100000"),
        period_from=date(2026, 4, 1),
        period_to=date(2026, 4, 30),
        cash_subaccount=cash_subaccount,
    )
    api = _client(hr_writer)
    r = api.post(f"/api/payroll/payouts/{payout.id}/cancel/", format="json")
    assert r.status_code == 400  # DRFValidationError("только для admin")


# ─── Edge cases ──────────────────────────────────────────────────────────


def test_set_rate_inserts_in_past(employee, uzs):
    """
    set_rate допускает вставку ставки задним числом — старые интервалы
    подрезаются, новая встаёт «между». Точный дубль даты — запрещён.
    """
    from django.core.exceptions import ValidationError

    from apps.payroll.services.rates import set_rate

    set_rate(
        employee=employee, amount=Decimal("100000"),
        effective_from=date(2026, 5, 1), currency=uzs,
    )
    set_rate(
        employee=employee, amount=Decimal("150000"),
        effective_from=date(2026, 4, 15), currency=uzs,
    )
    rates = list(SalaryRate.objects.filter(employee=employee).order_by("effective_from"))
    assert len(rates) == 2
    # Старая (4/15) закрылась 4/30 — на день раньше новой (5/1)
    assert rates[0].effective_from == date(2026, 4, 15)
    assert rates[0].effective_to == date(2026, 4, 30)
    # Текущая (5/1) осталась open-end
    assert rates[1].effective_from == date(2026, 5, 1)
    assert rates[1].effective_to is None

    # Дубль даты — запрещён
    with pytest.raises(ValidationError):
        set_rate(
            employee=employee, amount=Decimal("200000"),
            effective_from=date(2026, 5, 1), currency=uzs,
        )


def test_template_delete_blocked_with_active_assignments(
    hr_writer, employee, org,
):
    tpl = WorkScheduleTemplate.objects.create(
        organization=org, code="DEL-TEST",
        name="To delete", pattern_kind="weekday_mask",
        pattern={"weekdays": [0, 1], "start": "09:00", "end": "18:00", "duration_hours": 8},
    )
    WorkSchedule.objects.create(
        organization=org, employee=employee, template=tpl,
        effective_from=date(2026, 5, 1),
    )
    api = _client(hr_writer)
    r = api.delete(f"/api/payroll/schedule-templates/{tpl.id}/")
    assert r.status_code == 400, r.content
    assert WorkScheduleTemplate.objects.filter(id=tpl.id).exists()


def test_template_delete_ok_without_assignments(hr_writer, org):
    tpl = WorkScheduleTemplate.objects.create(
        organization=org, code="DEL-OK",
        name="ok", pattern_kind="weekday_mask",
        pattern={"weekdays": [0], "start": "09:00", "end": "18:00", "duration_hours": 8},
    )
    api = _client(hr_writer)
    r = api.delete(f"/api/payroll/schedule-templates/{tpl.id}/")
    assert r.status_code == 204
    assert not WorkScheduleTemplate.objects.filter(id=tpl.id).exists()
