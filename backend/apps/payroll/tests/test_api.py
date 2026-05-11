"""
Integration tests: HTTP-flow через DRF APIClient.

Покрытие:
    1. Полный happy-path: rate → shift → payout → balance.
    2. RBAC: без hr:r нет доступа.
    3. RBAC: финансовые поля скрыты для не-hr-юзера в /memberships.
    4. PaymentSerializer guard: kind=salary через /api/payments/ → 400.
    5. Расчёт баланса end-to-end.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounting.models import GLAccount, GLSubaccount
from apps.currency.models import Currency
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollPayout,
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
def cash_subaccount(org):
    return GLSubaccount.objects.get(account__organization=org, code="50.01")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


def _make_user(org, email, modules=None, joined=None):
    """Создать user + membership + права на модули. Возвращает (user, membership)."""
    u = User.objects.create(email=email, full_name=email.split("@")[0], is_active=True)
    u.set_password("x")
    u.save()
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="Test",
    )
    if joined is not None:
        OrganizationMembership.objects.filter(pk=m.pk).update(joined_at=joined)
        m.refresh_from_db()
    for mod_code, level in (modules or {}).items():
        UserModuleAccessOverride.objects.create(
            membership=m,
            module=Module.objects.get(code=mod_code),
            level=level,
        )
    return u, m


@pytest.fixture
def hr_admin(org):
    u, _ = _make_user(org, "hr-admin@test.local", {"hr": AccessLevel.ADMIN})
    return u


@pytest.fixture
def hr_reader(org):
    u, _ = _make_user(org, "hr-reader@test.local", {"hr": AccessLevel.READ})
    return u


@pytest.fixture
def no_hr_user(org):
    """Юзер с rw на feed (для cross-module /memberships endpoint), но без hr."""
    u, _ = _make_user(org, "feed-only@test.local", {"feed": AccessLevel.READ_WRITE})
    return u


@pytest.fixture
def employee(org, uzs):
    """Сотрудник на смене (per_shift), с joined_at в прошлом."""
    u, m = _make_user(
        org, "worker@test.local",
        joined=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    CompensationPlan.objects.update_or_create(
        employee=m,
        defaults={
            "organization": org,
            "compensation_type": CompensationPlan.Type.PER_SHIFT,
            "currency": uzs,
        },
    )
    return m


def _client(user, org_code="DEFAULT"):
    api = APIClient()
    api.force_authenticate(user=user)
    api.credentials(HTTP_X_ORGANIZATION_CODE=org_code)
    return api


# ─── Happy path ──────────────────────────────────────────────────────────


def test_full_payroll_flow(hr_admin, employee, uzs, cash_subaccount):
    """Rate → Shift → Payout → Balance — всё через HTTP."""
    api = _client(hr_admin)

    # 1. Установить ставку
    r = api.post(
        "/api/payroll/rates/",
        {
            "employee": str(employee.id),
            "amount": "200000",
            "currency": str(uzs.id),
            "effective_from": "2026-04-01",
            "reason": "hire",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    rate_id = r.json()["id"]
    assert SalaryRate.objects.get(pk=rate_id).effective_to is None

    # 2. Создать смену
    r = api.post(
        "/api/payroll/work-shifts/",
        {
            "employee": str(employee.id),
            "shift_date": "2026-04-15",
            "kind": "work",
            "hours": "8",
        },
        format="json",
    )
    assert r.status_code == 201, r.content

    # 3. Выплатить аванс
    r = api.post(
        "/api/payroll/payouts/",
        {
            "employee": str(employee.id),
            "type": "advance",
            "amount_uzs": "150000",
            "period_from": "2026-04-01",
            "period_to": "2026-04-15",
            "cash_subaccount": str(cash_subaccount.id),
            "channel": "cash",
            "on_date": "2026-04-15",
            "notes": "Аванс за апрель",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    payout = r.json()
    assert payout["payment_status"] == "posted"
    assert payout["amount_uzs"] == "150000.00"

    # 4. Баланс
    r = api.get(f"/api/payroll/employees/{employee.id}/balance/?as_of=2026-04-30")
    assert r.status_code == 200
    bal = r.json()
    # accrued = 200_000 (одна смена × ставка 200_000)
    assert Decimal(bal["accrued_total"]) == Decimal("200000")
    assert Decimal(bal["paid_total"]) == Decimal("150000")
    assert Decimal(bal["balance_uzs"]) == Decimal("50000")


# ─── RBAC ────────────────────────────────────────────────────────────────


def test_no_hr_blocks_payroll_endpoints(no_hr_user):
    """Юзер без hr:r не может читать payroll endpoints."""
    api = _client(no_hr_user)
    for path in (
        "/api/payroll/compensation-plans/",
        "/api/payroll/rates/",
        "/api/payroll/schedule-templates/",
        "/api/payroll/work-shifts/",
        "/api/payroll/payouts/",
    ):
        r = api.get(path)
        assert r.status_code == 403, f"{path}: {r.status_code}"


def test_hr_reader_can_read_but_not_write(hr_reader, employee, uzs):
    """hr:r видит, но не пишет."""
    api = _client(hr_reader)
    # Read OK
    r = api.get("/api/payroll/rates/")
    assert r.status_code == 200
    # Write 403
    r = api.post(
        "/api/payroll/rates/",
        {
            "employee": str(employee.id),
            "amount": "100000",
            "currency": str(uzs.id),
            "effective_from": "2026-04-01",
        },
        format="json",
    )
    assert r.status_code == 403


def test_membership_finance_fields_hidden_for_non_hr(no_hr_user, org):
    """no_hr_user видит самого себя в /memberships, но financial поля = null."""
    api = _client(no_hr_user)
    r = api.get("/api/memberships/?include_compensation=1&include_balance=1")
    assert r.status_code == 200
    # peer-filter: head видит как минимум самого себя
    own_membership = OrganizationMembership.objects.get(
        user=no_hr_user, organization=org,
    )
    found = next(
        (m for m in r.json()["results"] if m["id"] == str(own_membership.id)),
        None,
    )
    assert found is not None
    # Запрос содержит флаги, но юзер не имеет hr:r → null
    assert found["compensation_type"] is None
    assert found["current_rate_uzs"] is None
    assert found["balance_uzs"] is None


def test_membership_finance_fields_visible_for_hr(hr_admin, employee, uzs):
    SalaryRate.objects.create(
        organization=employee.organization, employee=employee,
        amount=Decimal("500000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    api = _client(hr_admin)
    r = api.get("/api/memberships/?include_compensation=1&include_balance=1")
    assert r.status_code == 200
    found = next(
        (m for m in r.json()["results"] if m["id"] == str(employee.id)),
        None,
    )
    assert found is not None
    assert found["compensation_type"] == "per_shift"
    assert found["current_rate_uzs"] == "500000.00"
    assert found["balance_uzs"] is not None


# ─── Payment guard ───────────────────────────────────────────────────────


def test_salary_payment_blocked_via_payments_api(hr_admin, cash_subaccount, org):
    """POST /api/payments/ с kind=salary → 400 (используйте /api/payroll/payouts/)."""
    api = _client(hr_admin)
    r = api.post(
        "/api/payments/",
        {
            "doc_number": "ПЛ-TEST-1",
            "date": "2026-05-01",
            "direction": "out",
            "channel": "cash",
            "kind": "salary",
            "amount_uzs": "100000",
            "cash_subaccount": str(cash_subaccount.id),
        },
        format="json",
    )
    assert r.status_code == 400, r.content
    assert "kind" in r.json() or "kind" in str(r.content)


# ─── Edge cases ──────────────────────────────────────────────────────────


def test_rate_history_close_previous_on_new(hr_admin, employee, uzs):
    """При создании новой ставки прошлая закрывается датой new.from − 1."""
    api = _client(hr_admin)
    api.post("/api/payroll/rates/", {
        "employee": str(employee.id),
        "amount": "100000",
        "currency": str(uzs.id),
        "effective_from": "2026-04-01",
    }, format="json")
    api.post("/api/payroll/rates/", {
        "employee": str(employee.id),
        "amount": "150000",
        "currency": str(uzs.id),
        "effective_from": "2026-05-01",
    }, format="json")
    rates = SalaryRate.objects.filter(employee=employee).order_by("effective_from")
    assert rates.count() == 2
    assert rates[0].effective_to == date(2026, 4, 30)
    assert rates[1].effective_to is None


def test_template_preview(hr_admin, org):
    """POST /api/payroll/schedule-templates/{id}/preview/ возвращает ожидаемые смены."""
    from apps.payroll.models import WorkScheduleTemplate
    tpl = WorkScheduleTemplate.objects.get(organization=org, code="STD-9-18")
    api = _client(hr_admin)
    r = api.post(
        f"/api/payroll/schedule-templates/{tpl.id}/preview/",
        {"from_date": "2026-05-04", "to_date": "2026-05-10"},
        format="json",
    )
    assert r.status_code == 200, r.content
    items = r.json()
    assert len(items) == 7
    # пн-пт = work, сб-вс = day_off
    assert [it["kind"] for it in items] == ["work"] * 5 + ["day_off"] * 2


def test_apply_template_bulk(hr_admin, employee, org):
    """POST /api/payroll/work-shifts/bulk/ генерирует смены из шаблона."""
    from apps.payroll.models import WorkScheduleTemplate
    tpl = WorkScheduleTemplate.objects.get(organization=org, code="STD-9-18")
    api = _client(hr_admin)
    r = api.post(
        "/api/payroll/work-shifts/bulk/",
        {
            "employee": str(employee.id),
            "template": str(tpl.id),
            "from_date": "2026-05-04",
            "to_date": "2026-05-10",
        },
        format="json",
    )
    assert r.status_code == 201, r.content
    assert r.json()["created"] == 7
    assert WorkShift.objects.filter(employee=employee).count() == 7


def test_employee_calendar(hr_admin, employee, org):
    """GET /api/payroll/employees/{id}/calendar/ возвращает expected+actual."""
    from apps.payroll.models import WorkScheduleTemplate, WorkSchedule
    tpl = WorkScheduleTemplate.objects.get(organization=org, code="STD-9-18")
    WorkSchedule.objects.create(
        organization=org, employee=employee, template=tpl,
        effective_from=date(2026, 5, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 5, 4), kind=WorkShift.Kind.VACATION,
        source=WorkShift.Source.MANUAL,
    )
    api = _client(hr_admin)
    r = api.get(
        f"/api/payroll/employees/{employee.id}/calendar/?from=2026-05-04&to=2026-05-10"
    )
    assert r.status_code == 200, r.content
    data = r.json()
    assert data["template_code"] == "STD-9-18"
    assert len(data["expected"]) == 7
    assert len(data["actual"]) == 1
    assert data["actual"][0]["kind"] == "vacation"
