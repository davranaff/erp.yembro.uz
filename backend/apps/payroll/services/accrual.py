"""
Расчёт начисленной зарплаты за период с учётом compensation_type и валюты ставки.

Multi-currency: SalaryRate.amount хранится в native currency (UZS, USD, EUR).
При расчёте каждый день конвертируется в UZS по курсу CBU на shift_date через
apps.payroll.services.fx.convert_to_uzs.
"""
from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, timedelta
from datetime import timedelta as _td
from decimal import Decimal
from typing import List, Optional

from django.core.exceptions import ValidationError

from ..models import CompensationPlan, WorkShift
from .compensation import compensation_type_at
from .fx import convert_to_uzs
from .rates import rate_at
from .schedule import expected_workdays_in_month, template_for_employee_on


def _standard_hours_per_day(template) -> Decimal:
    """
    Сколько часов в стандартной смене по шаблону. Берём pattern.duration_hours
    если есть (типично 8 или 12), иначе fallback 8. Используется для
    pro-rata начисления частичных дней (когда WorkShift.hours отличается).
    """
    if template is not None:
        pat = getattr(template, "pattern", None)
        if isinstance(pat, dict):
            dh = pat.get("duration_hours")
            if dh is not None:
                try:
                    val = Decimal(str(dh))
                    if val > 0:
                        return val
                except Exception:
                    pass
    return Decimal("8")


def _safe_convert(amount: Decimal, currency_code: str, on_date: date) -> Optional[Decimal]:
    """
    Конвертирует amount в UZS. Возвращает None если курс не найден
    (накопление идёт без этой строки — лучше пропустить, чем упасть).
    """
    try:
        result = convert_to_uzs(amount, currency_code, on_date)
        return result.amount_uzs
    except ValidationError:
        return None


def average_daily_earnings(employee, ref_date: date) -> Decimal:
    """
    Средний дневной заработок за 12 предшествующих месяцев (UZ ТК).

    Реализация: вызываем accrue_for_period за 12 мес и делим на число
    рабочих дней в этом периоде (через шаблон сотрудника или fallback).
    Это даёт корректный avg для всех типов компенсации (per_shift, per_hour,
    monthly_salary), включая случаи когда табель не заполнен явно.
    """
    period_from = ref_date - _td(days=365)
    period_to = ref_date - _td(days=1)

    if period_to < period_from:
        return Decimal("0")

    # Считаем рабочие дни через шаблон месяца за каждый месяц диапазона.
    # Если шаблона нет — fallback 22 дня в месяце × число месяцев.
    work_days_count = _count_work_days_in_range(employee, period_from, period_to)
    if work_days_count == 0:
        return Decimal("0")

    # Накопленный заработок за тот же интервал (без рекурсии — temp-call avoiding)
    earned = _accrued_for_avg(employee, period_from, period_to)
    return (earned / Decimal(work_days_count)).quantize(Decimal("0.01"))


def _count_work_days_in_range(employee, start: date, end: date) -> int:
    """
    Кол-во ожидаемых рабочих дней в [start, end] на основе шаблона.
    Используется для расчёта avg_daily_earnings.

    Если у сотрудника нет ни одного WorkSchedule в этот период (типичный
    случай для PER_SHIFT/PER_HOUR работника-без-шаблона) — считаем по
    фактическим work/overtime сменам в табеле. Это даёт корректный avg
    для сменников без расписания.
    """
    from ..models import WorkSchedule
    has_schedule = WorkSchedule.objects.filter(
        employee=employee, effective_from__lte=end,
    ).filter(
        models_q_or_to_isnull(end),
    ).exists()

    if not has_schedule:
        return WorkShift.objects.filter(
            employee=employee,
            shift_date__range=(start, end),
            kind__in=[WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME],
            shift_index=0,
        ).count()

    if end < start:
        return 0
    cnt = 0
    d = start
    while d <= end:
        tpl = template_for_employee_on(employee, d)
        if tpl is None:
            # Без шаблона на конкретную дату — fallback к weekday<5
            if d.weekday() < 5:
                cnt += 1
        else:
            from .schedule import expand_template
            ex = expand_template(tpl, d, d, apply_holidays=True)
            if ex and ex[0].kind == WorkShift.Kind.WORK:
                cnt += 1
        d += _td(days=1)
    return cnt


def models_q_or_to_isnull(end_date: date):
    """Q-фильтр: effective_to is NULL OR effective_to >= end_date."""
    from django.db.models import Q
    return Q(effective_to__isnull=True) | Q(effective_to__gte=end_date)


def _accrued_for_avg(employee, start: date, end: date) -> Decimal:
    """
    Сумма начислений за период без учёта vacation/sick (только work-доход).
    Используется внутри average_daily_earnings — отдельная функция чтобы
    избежать рекурсии (avg → accrue → avg).
    """
    from .schedule import expand_template

    total_uzs = Decimal("0")
    all_shifts: dict[date, WorkShift] = {
        s.shift_date: s
        for s in WorkShift.objects.filter(
            employee=employee,
            shift_date__range=(start, end),
            shift_index=0,
        )
    }
    d = start
    while d <= end:
        comp_type = compensation_type_at(employee, d) or CompensationPlan.Type.MONTHLY_SALARY
        rate = rate_at(employee, d)
        shift = all_shifts.get(d)
        marked = shift.kind if shift else None

        if rate is None or marked in (
            WorkShift.Kind.ABSENCE, WorkShift.Kind.DAY_OFF,
            WorkShift.Kind.VACATION, WorkShift.Kind.SICK_LEAVE,
            WorkShift.Kind.HOLIDAY,
        ):
            d += _td(days=1)
            continue

        currency_code = rate.currency.code if rate.currency_id else "UZS"

        if comp_type == CompensationPlan.Type.PER_SHIFT:
            if marked in (WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME):
                v = _safe_convert(rate.amount, currency_code, d)
                if v is not None:
                    total_uzs += v
        elif comp_type == CompensationPlan.Type.PER_HOUR:
            if marked in (WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME) and shift.hours:
                v = _safe_convert(rate.amount * shift.hours, currency_code, d)
                if v is not None:
                    total_uzs += v
        elif comp_type == CompensationPlan.Type.MONTHLY_SALARY:
            tpl = template_for_employee_on(employee, d)
            is_work = False
            if tpl is not None:
                ex = expand_template(tpl, d, d, apply_holidays=True)
                is_work = bool(ex) and ex[0].kind == WorkShift.Kind.WORK
            else:
                is_work = marked in (WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME)
            if is_work:
                wd = expected_workdays_in_month(
                    tpl, d, organization=employee.organization,
                ) or 22
                native = rate.amount / Decimal(wd)
                v = _safe_convert(native, currency_code, d)
                if v is not None:
                    total_uzs += v
        d += _td(days=1)
    return total_uzs


@dataclass
class AccrualLine:
    date: date
    rate_amount: Decimal      # native amount per unit (день/смена/час) в валюте ставки
    rate_currency: str        # код валюты ставки
    accrued_native: Decimal   # сколько начислено в native currency
    accrued: Decimal          # сколько начислено в UZS (после конвертации)
    exchange_rate: Decimal    # UZS за единицу currency на shift_date (1 если UZS)
    note: str = ""


@dataclass
class AccrualResult:
    employee_id: str
    period_from: date
    period_to: date
    compensation_type: str
    currency_code: str | None
    accrued_uzs: Decimal = Decimal("0")
    breakdown: List[AccrualLine] = field(default_factory=list)


def _plan(employee) -> CompensationPlan | None:
    return getattr(employee, "compensation_plan", None)


def accrue_for_period(
    employee, from_date: date, to_date: date
) -> AccrualResult:
    """
    Расчёт начислений за период. Использует compensation_type_at(emp, day) и
    convert_to_uzs(rate.amount, rate.currency, day) — для multi-currency ставок.
    """
    plan = _plan(employee)
    primary_type = plan.compensation_type if plan else CompensationPlan.Type.MONTHLY_SALARY
    currency_code = plan.currency.code if plan and plan.currency_id else None

    result = AccrualResult(
        employee_id=str(employee.id),
        period_from=from_date,
        period_to=to_date,
        compensation_type=primary_type,
        currency_code=currency_code,
    )
    if to_date < from_date:
        return result

    # Все смены за период (любого kind) — нужны для MONTHLY_SALARY чтобы
    # отличать absence/vacation от "ничего не отмечено" (по умолчанию work).
    all_shifts_by_date: dict[date, WorkShift] = {
        s.shift_date: s
        for s in WorkShift.objects.filter(
            employee=employee,
            shift_date__range=(from_date, to_date),
            shift_index=0,
        )
    }

    # Cache "сколько прогулов в этом месяце" (для MONTHLY_SALARY новая логика):
    # 0 прогулов → платим за все календарные дни (rate / days_in_month);
    # ≥1 прогул → переключаемся на rate / working_days_in_month, и за
    # выходные/праздники по шаблону не платим. Считаем по календарному
    # месяцу (а не period), потому что user рассуждает в терминах
    # «прогулов за месяц», а не за произвольный отрезок.
    absences_in_month_cache: dict[tuple[int, int], int] = {}

    def _absences_in_month(year: int, month: int) -> int:
        key = (year, month)
        if key not in absences_in_month_cache:
            last_day = monthrange(year, month)[1]
            absences_in_month_cache[key] = WorkShift.objects.filter(
                employee=employee,
                shift_date__gte=date(year, month, 1),
                shift_date__lte=date(year, month, last_day),
                shift_index=0,
                kind=WorkShift.Kind.ABSENCE,
            ).count()
        return absences_in_month_cache[key]

    d = from_date
    total_uzs = Decimal("0")
    while d <= to_date:
        comp_type = compensation_type_at(employee, d) or primary_type
        rate = rate_at(employee, d)
        shift = all_shifts_by_date.get(d)
        # Тип смены в табеле (None если день не отмечен).
        marked_kind = shift.kind if shift else None

        # Отпуск/больничный/праздник — по среднему дневному (уже в UZS).
        if marked_kind in (
            WorkShift.Kind.VACATION,
            WorkShift.Kind.SICK_LEAVE,
            WorkShift.Kind.HOLIDAY,
        ):
            avg = average_daily_earnings(employee, d)
            if avg > 0:
                total_uzs += avg
                result.breakdown.append(AccrualLine(
                    date=d,
                    rate_amount=avg,
                    rate_currency="UZS",
                    accrued_native=avg,
                    accrued=avg,
                    exchange_rate=Decimal("1"),
                    note=f"avg ({marked_kind})",
                ))
            d += timedelta(days=1)
            continue

        # Прогул / явный выходной — 0
        if marked_kind in (WorkShift.Kind.ABSENCE, WorkShift.Kind.DAY_OFF):
            d += timedelta(days=1)
            continue

        if rate is None:
            d += timedelta(days=1)
            continue

        rate_currency = rate.currency.code if rate.currency_id else "UZS"

        if comp_type == CompensationPlan.Type.MONTHLY_SALARY:
            # Новая логика (см. услов. оплаты по новым правилам):
            #   - 0 прогулов за месяц → платим за все КАЛЕНДАРНЫЕ дни
            #     (включая вс/праздник). Дневная ставка = rate / days_in_month.
            #   - ≥1 прогул → переключаемся на старый «по рабочим дням»:
            #     платим только за work/overtime + рабочие дни шаблона.
            #     Дневная ставка = rate / working_days_in_month.
            # Pro-rata по часам (WorkShift.hours): дневная × hours/std_hours,
            # где std_hours = pattern.duration_hours (или 8 если шаблона нет).
            tpl = template_for_employee_on(employee, d)
            misses = _absences_in_month(d.year, d.month)
            std_hours = _standard_hours_per_day(tpl)
            mode_lbl: str
            day_native: Decimal | None = None
            is_paid_day: bool

            if misses == 0:
                # Calendar-mode: каждый день месяца оплачивается.
                days_in_month = monthrange(d.year, d.month)[1]
                day_native = rate.amount / Decimal(days_in_month)
                is_paid_day = True
                mode_lbl = f"calendar 1/{days_in_month}"
            else:
                wd = expected_workdays_in_month(
                    tpl, d, organization=employee.organization,
                ) or 22
                day_native = rate.amount / Decimal(wd)
                # Этот день — рабочий?
                if tpl is not None:
                    from .schedule import expand_template
                    expected = expand_template(tpl, d, d, apply_holidays=True)
                    is_paid_day = bool(expected) and expected[0].kind == WorkShift.Kind.WORK
                else:
                    # Без шаблона — оплачиваем только если в табеле явный work/overtime
                    is_paid_day = marked_kind in (
                        WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME,
                    )
                mode_lbl = f"work-day 1/{wd}"

            if is_paid_day and day_native is not None:
                # Pro-rata по часам: если у смены задано hours, и оно
                # отличается от стандарта — берём пропорционально.
                hours_note = ""
                if shift is not None and shift.hours is not None and shift.hours > 0:
                    if std_hours > 0:
                        factor = Decimal(shift.hours) / std_hours
                        if factor != Decimal("1"):
                            day_native = day_native * factor
                            hours_note = f" {shift.hours}/{std_hours}h"

                day_native = day_native.quantize(Decimal("0.01"))
                fx = _convert_or_none(day_native, rate_currency, d)
                if fx is None:
                    d += timedelta(days=1)
                    continue
                total_uzs += fx.amount_uzs
                source = "template" if marked_kind is None else "manual"
                result.breakdown.append(AccrualLine(
                    date=d,
                    rate_amount=rate.amount,
                    rate_currency=rate_currency,
                    accrued_native=day_native,
                    accrued=fx.amount_uzs,
                    exchange_rate=fx.exchange_rate,
                    note=(
                        f"monthly {mode_lbl} ({source}){hours_note}"
                        + (f" @ {rate_currency}" if rate_currency != "UZS" else "")
                    ),
                ))
        elif comp_type == CompensationPlan.Type.PER_SHIFT:
            if shift is not None and marked_kind in (WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME):
                fx = _convert_or_none(rate.amount, rate_currency, d)
                if fx is None:
                    d += timedelta(days=1)
                    continue
                total_uzs += fx.amount_uzs
                result.breakdown.append(AccrualLine(
                    date=d,
                    rate_amount=rate.amount,
                    rate_currency=rate_currency,
                    accrued_native=rate.amount,
                    accrued=fx.amount_uzs,
                    exchange_rate=fx.exchange_rate,
                    note=shift.get_kind_display() + (f" @ {rate_currency}" if rate_currency != "UZS" else ""),
                ))
        elif comp_type == CompensationPlan.Type.PER_HOUR:
            if (
                shift is not None
                and marked_kind in (WorkShift.Kind.WORK, WorkShift.Kind.OVERTIME)
                and shift.hours is not None
            ):
                line_native = (rate.amount * shift.hours).quantize(Decimal("0.01"))
                fx = _convert_or_none(line_native, rate_currency, d)
                if fx is None:
                    d += timedelta(days=1)
                    continue
                total_uzs += fx.amount_uzs
                result.breakdown.append(AccrualLine(
                    date=d,
                    rate_amount=rate.amount,
                    rate_currency=rate_currency,
                    accrued_native=line_native,
                    accrued=fx.amount_uzs,
                    exchange_rate=fx.exchange_rate,
                    note=f"{shift.hours} ч" + (f" @ {rate_currency}" if rate_currency != "UZS" else ""),
                ))
        d += timedelta(days=1)

    result.accrued_uzs = total_uzs
    return result


def _convert_or_none(amount: Decimal, currency_code: str, on_date: date):
    """Wrapper: возвращает FXConversion или None при отсутствии курса."""
    try:
        return convert_to_uzs(amount, currency_code, on_date)
    except ValidationError:
        return None
