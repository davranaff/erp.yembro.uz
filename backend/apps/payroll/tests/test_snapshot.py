"""
Тесты PayrollAccrualSnapshot: refresh + fallback.
"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from django.utils import timezone as dj_tz

from apps.currency.models import Currency
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    PayrollAccrualSnapshot,
    SalaryRate,
    WorkShift,
)
from apps.payroll.services.snapshot import (
    get_balance_via_snapshot,
    refresh_balance_snapshots,
)
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def employee(org, uzs):
    u = User.objects.create(email="snap@t.l", full_name="W", is_active=True)
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
        amount=Decimal("100000"), currency=uzs,
        effective_from=date(2026, 4, 1),
    )
    WorkShift.objects.create(
        organization=org, employee=m,
        shift_date=date(2026, 4, 5), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    return m


def test_refresh_creates_snapshot(employee, org):
    n = refresh_balance_snapshots(organization=org)
    assert n >= 1
    snap = PayrollAccrualSnapshot.objects.get(employee=employee)
    assert snap.balance_uzs > 0


def test_refresh_updates_existing(employee, org):
    refresh_balance_snapshots(organization=org)
    initial = PayrollAccrualSnapshot.objects.get(employee=employee)
    initial_balance = initial.balance_uzs

    # Добавляем смену → баланс растёт
    WorkShift.objects.create(
        organization=org, employee=employee,
        shift_date=date(2026, 4, 6), kind=WorkShift.Kind.WORK,
        source=WorkShift.Source.MANUAL,
    )
    refresh_balance_snapshots(organization=org)
    updated = PayrollAccrualSnapshot.objects.get(employee=employee)
    assert updated.balance_uzs > initial_balance


def test_get_balance_via_snapshot_uses_fresh(employee, org):
    refresh_balance_snapshots(organization=org)
    today = date.today()
    # Вызываем with как-of=today — но snapshot имеет today as_of (auto)
    # для теста зафиксируем
    snap = PayrollAccrualSnapshot.objects.get(employee=employee)
    bal = get_balance_via_snapshot(employee, snap.as_of)
    assert bal.balance_uzs == snap.balance_uzs


def test_get_balance_falls_back_when_stale(employee, org):
    """Если snapshot старее max_age_hours — берём live."""
    refresh_balance_snapshots(organization=org)
    snap = PayrollAccrualSnapshot.objects.get(employee=employee)
    # Вручную делаем snapshot старым
    PayrollAccrualSnapshot.objects.filter(pk=snap.pk).update(
        computed_at=dj_tz.now() - timedelta(days=2),
    )
    bal = get_balance_via_snapshot(employee, snap.as_of, max_age_hours=24)
    # Snapshot старый → live-расчёт. Значение совпадёт (нет новых данных),
    # но computed свежий — проверяем что метод не упал.
    assert bal.balance_uzs > 0
