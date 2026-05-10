from datetime import date
from decimal import Decimal

import pytest

from apps.payroll.models import WorkScheduleTemplate, WorkShift
from apps.payroll.services.schedule import (
    apply_template_to_period,
    expand_template,
    expected_workdays_in_month,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def tpl_weekday(org):
    return WorkScheduleTemplate.objects.create(
        organization=org, code="TST-WD",
        name="пн-пт 9-18",
        pattern_kind=WorkScheduleTemplate.PatternKind.WEEKDAY_MASK,
        pattern={
            "weekdays": [0, 1, 2, 3, 4],
            "start": "09:00",
            "end": "18:00",
            "duration_hours": 8,
        },
    )


@pytest.fixture
def tpl_rotation(org):
    return WorkScheduleTemplate.objects.create(
        organization=org, code="TST-ROT",
        name="2/2 12 часов",
        pattern_kind=WorkScheduleTemplate.PatternKind.ROTATION,
        pattern={
            "work_days": 2,
            "rest_days": 2,
            "anchor_date": "2026-05-04",  # Mon
            "start": "08:00",
            "end": "20:00",
            "duration_hours": 12,
        },
    )


def test_expand_weekday_mask(tpl_weekday):
    # Без апгрейда holidays — берём интервал без UZ-праздников.
    # 11-17 мая 2026: 11 пн … 15 пт работа, 16-17 сб-вс выходные.
    out = expand_template(tpl_weekday, date(2026, 5, 11), date(2026, 5, 17))
    assert len(out) == 7
    kinds = [e.kind for e in out]
    assert kinds == ["work"] * 5 + ["day_off"] * 2


def test_expand_rotation_2_2(tpl_rotation):
    # anchor 4 мая (Mon), 2/2 → 4,5 work; 6,7 off; 8,9 work (но 9 — праздник UZ);
    # Берём apply_holidays=False чтобы тестировать чистую логику ротации.
    out = expand_template(tpl_rotation, date(2026, 5, 4), date(2026, 5, 11), apply_holidays=False)
    kinds = [e.kind for e in out]
    assert kinds == ["work", "work", "day_off", "day_off",
                     "work", "work", "day_off", "day_off"]


def test_expand_rotation_with_holiday(tpl_rotation):
    """С apply_holidays=True 9 мая (День памяти) → HOLIDAY вместо WORK."""
    out = expand_template(tpl_rotation, date(2026, 5, 4), date(2026, 5, 11))
    # 9 мая был бы work-день в ротации (8-9 work)
    target = next(e for e in out if e.date == date(2026, 5, 9))
    assert target.kind == "holiday"


def test_expected_workdays_in_month_weekday(tpl_weekday):
    # Май 2026: 31 день, 21 пн-пт = 21 рабочих
    assert expected_workdays_in_month(tpl_weekday, date(2026, 5, 1)) == 21


def test_expected_workdays_fallback_when_no_template():
    assert expected_workdays_in_month(None, date(2026, 5, 1)) == 22


def test_apply_template_creates_shifts(employee_monthly, tpl_weekday):
    # 11-17 мая — без UZ-праздников
    n = apply_template_to_period(
        employee=employee_monthly,
        template=tpl_weekday,
        from_date=date(2026, 5, 11),
        to_date=date(2026, 5, 17),
    )
    assert n == 7
    shifts = list(WorkShift.objects.filter(employee=employee_monthly).order_by("shift_date"))
    assert len(shifts) == 7
    work_shifts = [s for s in shifts if s.kind == WorkShift.Kind.WORK]
    assert len(work_shifts) == 5
    assert all(s.source == WorkShift.Source.TEMPLATE for s in shifts)


def test_apply_template_does_not_overwrite(employee_monthly, tpl_weekday):
    # руками отметили 12 мая как ОТПУСК
    WorkShift.objects.create(
        organization=employee_monthly.organization,
        employee=employee_monthly,
        shift_date=date(2026, 5, 12),
        kind=WorkShift.Kind.VACATION,
        source=WorkShift.Source.MANUAL,
    )
    n = apply_template_to_period(
        employee=employee_monthly,
        template=tpl_weekday,
        from_date=date(2026, 5, 11),
        to_date=date(2026, 5, 17),
    )
    assert n == 6  # 12 мая не перезаписывается
    s = WorkShift.objects.get(employee=employee_monthly, shift_date=date(2026, 5, 12))
    assert s.kind == WorkShift.Kind.VACATION
    assert s.source == WorkShift.Source.MANUAL


def test_pattern_validation_errors(org):
    from django.core.exceptions import ValidationError

    tpl = WorkScheduleTemplate(
        organization=org, code="X", name="X",
        pattern_kind=WorkScheduleTemplate.PatternKind.WEEKDAY_MASK,
        pattern={"weekdays": [], "start": "09:00", "end": "18:00", "duration_hours": 8},
    )
    with pytest.raises(ValidationError):
        tpl.full_clean()
