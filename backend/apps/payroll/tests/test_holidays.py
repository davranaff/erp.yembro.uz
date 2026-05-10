"""
Тесты праздников: интеграция в expand_template и expected_workdays_in_month.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.currency.models import Currency
from apps.modules.models import Module
from apps.organizations.models import Organization, OrganizationMembership
from apps.payroll.models import (
    CompensationPlan,
    Holiday,
    SalaryRate,
    WorkScheduleTemplate,
    WorkShift,
)
from apps.payroll.services.accrual import accrue_for_period
from apps.payroll.services.schedule import (
    expand_template,
    expected_workdays_in_month,
)
from apps.rbac.models import AccessLevel, UserModuleAccessOverride
from apps.users.models import User
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def uzs():
    return Currency.objects.get(code="UZS")


@pytest.fixture
def tpl_weekday(org):
    return WorkScheduleTemplate.objects.create(
        organization=org, code="HOL-TST",
        name="пн-пт 9-18",
        pattern_kind=WorkScheduleTemplate.PatternKind.WEEKDAY_MASK,
        pattern={
            "weekdays": [0, 1, 2, 3, 4],
            "start": "09:00", "end": "18:00", "duration_hours": 8,
        },
    )


def test_uz_holidays_seeded():
    """Сидер 2026 создаёт глобальные праздники."""
    assert Holiday.objects.filter(
        organization__isnull=True, date=date(2026, 1, 1),
    ).exists()
    assert Holiday.objects.filter(
        organization__isnull=True, date=date(2026, 9, 1),
    ).exists()


def test_expand_template_marks_holiday(tpl_weekday):
    """Рабочий день, попавший на праздник, помечается HOLIDAY."""
    # 2026-09-01 — День независимости (вторник, рабочий по шаблону)
    out = expand_template(tpl_weekday, date(2026, 9, 1), date(2026, 9, 2))
    assert out[0].date == date(2026, 9, 1)
    assert out[0].kind == WorkShift.Kind.HOLIDAY
    assert out[1].kind == WorkShift.Kind.WORK  # обычный вторник… 9-2 = ср


def test_expected_workdays_excludes_holidays(tpl_weekday, org):
    """В месяце с праздником рабочих дней на 1 меньше при том же числе пн-пт."""
    # Декабрь 2026: 23 пн-пт (с 1 по 31, начинается со вторника). 8 декабря вт — праздник Конституции.
    wd_dec = expected_workdays_in_month(tpl_weekday, date(2026, 12, 15))
    assert wd_dec == 22  # 23 - 1 праздник

    # Январь 2026: 22 пн-пт. 1 янв чт + 2 янв пт — праздники = 22 - 2 = 20
    wd_jan = expected_workdays_in_month(tpl_weekday, date(2026, 1, 15))
    assert wd_jan == 20


def test_org_specific_holiday_overrides(tpl_weekday, org):
    """Организационный праздник тоже учитывается."""
    Holiday.objects.create(
        organization=org, date=date(2026, 7, 1),
        name="Корпоративный праздник", is_paid=True,
    )
    out = expand_template(tpl_weekday, date(2026, 7, 1), date(2026, 7, 1))
    assert out[0].kind == WorkShift.Kind.HOLIDAY


def test_accrue_pro_rated_uses_holidays(org, uzs, tpl_weekday):
    """В месяце с меньшим числом рабочих дней дневная доля больше."""
    from apps.payroll.models import WorkSchedule

    u = User.objects.create(email="hol-emp@test.local", full_name="Emp", is_active=True)
    m = OrganizationMembership.objects.create(
        user=u, organization=org, is_active=True, position_title="Director",
    )
    OrganizationMembership.objects.filter(pk=m.pk).update(
        joined_at=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    m.refresh_from_db()
    CompensationPlan.objects.create(
        organization=org, employee=m,
        compensation_type=CompensationPlan.Type.MONTHLY_SALARY,
        currency=uzs,
    )
    SalaryRate.objects.create(
        organization=org, employee=m,
        amount=Decimal("4400000"), currency=uzs,
        effective_from=date(2026, 1, 1),
    )
    WorkSchedule.objects.create(
        organization=org, employee=m, template=tpl_weekday,
        effective_from=date(2026, 1, 1),
    )
    # Декабрь 2026: 23 пн-пт, минус 8 декабря (праздник) = 22 рабочих.
    # MONTHLY_SALARY с шаблоном начисляет за каждый рабочий день шаблона
    # автоматически (даже без явных work-смен в табеле).
    # 22 дня × (4_400_000 / 22) = 4_400_000.
    res = accrue_for_period(m, date(2026, 12, 1), date(2026, 12, 31))
    assert res.accrued_uzs == Decimal("4400000.00")
    # Проверяем что 8 декабря (праздник) не попало в начисления
    breakdown_dates = {ln.date for ln in res.breakdown}
    assert date(2026, 12, 8) not in breakdown_dates


# ─── API ─────────────────────────────────────────────────────────────────


@pytest.fixture
def hr_admin(org):
    u = User.objects.create(email="hol-admin@test.local", full_name="A", is_active=True)
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


def test_list_holidays_includes_global_and_org(hr_admin, org):
    Holiday.objects.create(
        organization=org, date=date(2026, 7, 1),
        name="Местный", is_paid=True,
    )
    api = _client(hr_admin)
    r = api.get("/api/payroll/holidays/")
    assert r.status_code == 200
    dates = [h["date"] for h in r.json()["results"]]
    assert "2026-01-01" in dates  # global
    assert "2026-07-01" in dates  # org


def test_cannot_delete_global_holiday(hr_admin):
    api = _client(hr_admin)
    holiday = Holiday.objects.filter(
        organization__isnull=True, date=date(2026, 1, 1),
    ).first()
    r = api.delete(f"/api/payroll/holidays/{holiday.id}/")
    assert r.status_code == 400
    assert Holiday.objects.filter(pk=holiday.pk).exists()


def test_can_create_org_holiday(hr_admin):
    api = _client(hr_admin)
    r = api.post("/api/payroll/holidays/", {
        "date": "2026-07-15",
        "name": "Корпоратив",
        "is_paid": False,
    }, format="json")
    assert r.status_code == 201, r.content
    assert Holiday.objects.filter(date=date(2026, 7, 15)).exists()
