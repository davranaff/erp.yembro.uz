"""
Шаблоны графиков и генерация ожидаемых смен.

Pattern семантика:
    WEEKDAY_MASK:
        {"weekdays": [0..6], "start": "HH:MM", "end": "HH:MM",
         "duration_hours": <number>}
        Monday=0..Sunday=6.

    ROTATION:
        {"work_days": int>0, "rest_days": int>=0,
         "anchor_date": "YYYY-MM-DD",
         "start": "HH:MM", "end": "HH:MM",
         "duration_hours": <number>}
        День N от anchor_date: если (N % cycle) < work_days → WORK,
        иначе DAY_OFF. cycle = work_days + rest_days.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import List

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ..models import WorkScheduleTemplate, WorkShift


@dataclass
class ExpectedShift:
    date: date
    start_time: time | None
    end_time: time | None
    duration_hours: Decimal
    kind: str  # WorkShift.Kind value: "work" | "day_off"


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


def validate_pattern(pattern_kind: str, pattern: dict) -> None:
    """Проверка формы pattern — вызывается из model.clean() и serializer."""
    if not isinstance(pattern, dict):
        raise ValidationError({"pattern": "Pattern должен быть объектом."})
    if pattern_kind == WorkScheduleTemplate.PatternKind.WEEKDAY_MASK:
        weekdays = pattern.get("weekdays")
        if (
            not isinstance(weekdays, list)
            or not weekdays
            or any(not isinstance(d, int) or d < 0 or d > 6 for d in weekdays)
        ):
            raise ValidationError(
                {"pattern": "weekdays — непустой список int 0..6 (Mon..Sun)."}
            )
        for k in ("start", "end"):
            v = pattern.get(k)
            if not isinstance(v, str) or len(v) != 5:
                raise ValidationError({"pattern": f"{k} должен быть 'HH:MM'."})
            try:
                _parse_hhmm(v)
            except ValueError:
                raise ValidationError({"pattern": f"{k} некорректный 'HH:MM'."})
        if not isinstance(pattern.get("duration_hours"), (int, float)) or pattern["duration_hours"] <= 0:
            raise ValidationError({"pattern": "duration_hours > 0."})
    elif pattern_kind == WorkScheduleTemplate.PatternKind.ROTATION:
        for f in ("work_days", "rest_days"):
            v = pattern.get(f)
            if not isinstance(v, int) or v < 0:
                raise ValidationError({"pattern": f"{f} — int >= 0."})
        if pattern.get("work_days", 0) <= 0:
            raise ValidationError({"pattern": "work_days > 0."})
        anchor = pattern.get("anchor_date")
        if not isinstance(anchor, str):
            raise ValidationError({"pattern": "anchor_date — строка YYYY-MM-DD."})
        try:
            datetime.strptime(anchor, "%Y-%m-%d").date()
        except ValueError:
            raise ValidationError({"pattern": "anchor_date — формат YYYY-MM-DD."})
        for k in ("start", "end"):
            v = pattern.get(k)
            if not isinstance(v, str) or len(v) != 5:
                raise ValidationError({"pattern": f"{k} должен быть 'HH:MM'."})
            try:
                _parse_hhmm(v)
            except ValueError:
                raise ValidationError({"pattern": f"{k} некорректный 'HH:MM'."})
        if not isinstance(pattern.get("duration_hours"), (int, float)) or pattern["duration_hours"] <= 0:
            raise ValidationError({"pattern": "duration_hours > 0."})
    else:
        raise ValidationError({"pattern_kind": f"Неизвестный pattern_kind={pattern_kind}."})


def expand_template(
    template: WorkScheduleTemplate, from_date: date, to_date: date,
    *, apply_holidays: bool = True,
) -> List[ExpectedShift]:
    """
    Возвращает ожидаемые смены за интервал [from_date, to_date] согласно шаблону.
    Если apply_holidays=True — рабочие дни, попавшие на праздники
    (глобальные UZ + организационные), помечаются как HOLIDAY.
    Не сохраняет в БД.
    """
    if to_date < from_date:
        return []
    pat = template.pattern
    kind_field = template.pattern_kind
    duration = Decimal(str(pat.get("duration_hours") or 0))
    start_t = _parse_hhmm(pat["start"])
    end_t = _parse_hhmm(pat["end"])

    holidays = (
        get_holiday_dates(template.organization, from_date, to_date)
        if apply_holidays else set()
    )

    out: List[ExpectedShift] = []

    def _add(d: date, is_workday: bool) -> None:
        if is_workday and d in holidays:
            out.append(ExpectedShift(
                date=d, start_time=None, end_time=None,
                duration_hours=Decimal("0"),
                kind=WorkShift.Kind.HOLIDAY,
            ))
            return
        out.append(ExpectedShift(
            date=d,
            start_time=start_t if is_workday else None,
            end_time=end_t if is_workday else None,
            duration_hours=duration if is_workday else Decimal("0"),
            kind=WorkShift.Kind.WORK if is_workday else WorkShift.Kind.DAY_OFF,
        ))

    if kind_field == WorkScheduleTemplate.PatternKind.WEEKDAY_MASK:
        weekdays = set(pat["weekdays"])
        d = from_date
        while d <= to_date:
            _add(d, d.weekday() in weekdays)
            d += timedelta(days=1)
    elif kind_field == WorkScheduleTemplate.PatternKind.ROTATION:
        anchor = datetime.strptime(pat["anchor_date"], "%Y-%m-%d").date()
        cycle = int(pat["work_days"]) + int(pat["rest_days"])
        if cycle <= 0:
            return []
        work_days = int(pat["work_days"])
        d = from_date
        while d <= to_date:
            offset = (d - anchor).days % cycle
            _add(d, 0 <= offset < work_days)
            d += timedelta(days=1)
    return out


def get_holiday_dates(organization, from_date: date, to_date: date) -> set[date]:
    """
    Возвращает множество дат праздников в [from, to] для организации.
    Включает глобальные (organization=NULL) + организационные.
    """
    from django.db.models import Q

    from ..models import Holiday

    qs = Holiday.objects.filter(date__range=(from_date, to_date)).filter(
        Q(organization__isnull=True) | Q(organization=organization)
    )
    return set(qs.values_list("date", flat=True))


def expected_workdays_in_month(
    template: WorkScheduleTemplate | None, on_date: date,
    organization=None,
) -> int:
    """
    Сколько рабочих дней в месяце даты `on_date` по шаблону, минус праздники.
    Fallback 22 рабочих дня (если template=None).

    Если organization передана — праздники из Holiday вычитаются.
    expand_template сам помечает holiday-дни как HOLIDAY (kind != WORK),
    так что достаточно посчитать WORK-смены.
    """
    first = on_date.replace(day=1)
    if first.month == 12:
        last = first.replace(year=first.year + 1, month=1) - timedelta(days=1)
    else:
        last = first.replace(month=first.month + 1) - timedelta(days=1)

    if template is None:
        # Без шаблона — приблизительно 22 рабочих дня минус праздники месяца.
        if organization is None:
            return 22
        return max(0, 22 - len(get_holiday_dates(organization, first, last)))

    expected = expand_template(template, first, last)
    return sum(1 for e in expected if e.kind == WorkShift.Kind.WORK)


def auto_detect_overtime(employee, shift: WorkShift) -> bool:
    """
    Если у сотрудника есть активный шаблон на shift.shift_date и
    shift.hours > template.pattern["duration_hours"] — возвращает True
    (вызывающий должен превратить смену в OVERTIME).
    """
    if shift.kind not in (WorkShift.Kind.WORK,):
        return False
    if shift.hours is None:
        return False
    template = template_for_employee_on(employee, shift.shift_date)
    if template is None:
        return False
    pat = template.pattern or {}
    standard_hours = pat.get("duration_hours")
    if standard_hours is None:
        return False
    try:
        from decimal import Decimal as _D
        return shift.hours > _D(str(standard_hours))
    except Exception:
        return False


def template_for_employee_on(
    employee, on_date: date
) -> WorkScheduleTemplate | None:
    """Шаблон, активный на сотруднике в указанную дату (через WorkSchedule)."""
    from django.db.models import Q

    from ..models import WorkSchedule

    ws = (
        WorkSchedule.objects.filter(employee=employee, effective_from__lte=on_date)
        .filter(Q(effective_to__isnull=True) | Q(effective_to__gte=on_date))
        .select_related("template")
        .order_by("-effective_from")
        .first()
    )
    return ws.template if ws else None


@transaction.atomic
def apply_template_to_period(
    *,
    employee,
    template: WorkScheduleTemplate,
    from_date: date,
    to_date: date,
    user=None,
) -> int:
    """
    Bulk-create WorkShift(source=TEMPLATE) для каждой даты из expand_template.
    Не перезаписывает существующие смены (любого источника) на этих датах.
    Возвращает кол-во созданных.
    """
    expected = expand_template(template, from_date, to_date)
    existing_dates = set(
        WorkShift.objects.filter(
            employee=employee, shift_date__range=(from_date, to_date),
        ).values_list("shift_date", flat=True)
    )
    org = employee.organization
    tz = timezone.get_current_timezone()

    to_create = []
    for e in expected:
        if e.date in existing_dates:
            continue
        start_at = end_at = None
        if e.start_time and e.end_time:
            start_at = timezone.make_aware(
                datetime.combine(e.date, e.start_time), timezone=tz,
            )
            end_dt = datetime.combine(e.date, e.end_time)
            if e.end_time <= e.start_time:
                end_dt = end_dt + timedelta(days=1)
            end_at = timezone.make_aware(end_dt, timezone=tz)
        to_create.append(
            WorkShift(
                organization=org,
                employee=employee,
                shift_date=e.date,
                kind=e.kind,
                source=WorkShift.Source.TEMPLATE,
                source_template=template,
                start_at=start_at,
                end_at=end_at,
                hours=e.duration_hours if e.duration_hours > 0 else None,
                created_by=user,
            )
        )
    if to_create:
        WorkShift.objects.bulk_create(to_create)
    return len(to_create)
