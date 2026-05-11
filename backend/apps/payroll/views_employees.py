"""
Function-based views для read-only employee endpoints (balance, accrued, calendar).
Не CRUD — поэтому отдельным модулем, без OrgScopedModelViewSet.
"""
from __future__ import annotations

from datetime import datetime

from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError as DRFValidationError,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import _effective_level, level_satisfies
from apps.organizations.models import OrganizationMembership

from .models import WorkShift
from .services.accrual import accrue_for_period
from .services.balance import compute_balance
from .services.schedule import expand_template, template_for_employee_on


# ───────────────────────── helpers ─────────────────────────


def _resolve_org_membership(request):
    """Шорткат: повторяет логику OrganizationContextMixin для FBV."""
    code = request.META.get("HTTP_X_ORGANIZATION_CODE", "").strip()
    if not code:
        raise DRFValidationError({"detail": "Заголовок X-Organization-Code обязателен."})
    from apps.organizations.models import Organization

    try:
        org = Organization.objects.get(code=code, is_active=True)
    except Organization.DoesNotExist:
        raise NotFound({"detail": f"Организация '{code}' не найдена."})

    membership = (
        OrganizationMembership.objects.filter(
            user=request.user, organization=org, is_active=True
        ).first()
    )
    if membership is None:
        raise PermissionDenied({"detail": "Нет доступа к организации."})
    request.organization = org
    request.membership = membership
    return org, membership


def _require_hr_read(membership):
    """Проверка: есть ли у membership доступ к hr на чтение."""
    actual = _effective_level(membership, "hr")
    if not level_satisfies(actual, "r"):
        raise PermissionDenied(
            {"detail": "Недостаточно прав на чтение HR-данных (требуется hr:r)."}
        )


def _require_hr_or_self(membership, target_membership):
    """
    Доступ к данным целевого сотрудника:
        - hr:r → любого
        - сам себя — без hr (self-service)
    """
    if membership.id == target_membership.id:
        return
    actual = _effective_level(membership, "hr")
    if not level_satisfies(actual, "r"):
        raise PermissionDenied(
            {"detail": "Можно смотреть только свой баланс или иметь hr:r."}
        )


def _employee_or_404(org, pk):
    try:
        return OrganizationMembership.objects.select_related("user").get(
            pk=pk, organization=org,
        )
    except OrganizationMembership.DoesNotExist:
        raise NotFound({"employee": "Сотрудник не найден."})


def _parse_date(value, name):
    if not value:
        raise DRFValidationError({name: "Параметр обязателен (YYYY-MM-DD)."})
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise DRFValidationError({name: "Формат YYYY-MM-DD."})


# ───────────────────────── endpoints ─────────────────────────


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def all_balances(request):
    """
    GET /api/payroll/balances/?as_of=YYYY-MM-DD&include_inactive=1

    Bulk-сводка по всем сотрудникам:
      - rows[]: per-employee balance + явка за текущий месяц
      - monthly_fund[]: фонд ЗП по 12 месяцам (начислено + выплачено)
      - totals: общие итоги

    Сортировка строк: по убыванию долга компании.
    """
    from datetime import date as _date, timedelta as _timedelta
    from decimal import Decimal as _D

    from django.db.models import Sum

    from apps.payments.models import Payment
    from apps.payroll.models import PayrollPayout, WorkShift
    from apps.payroll.services.accrual import accrue_for_period

    org, membership = _resolve_org_membership(request)
    _require_hr_read(membership)

    as_of_str = request.query_params.get("as_of")
    as_of = _parse_date(as_of_str, "as_of") if as_of_str else _date.today()

    include_inactive = request.query_params.get("include_inactive") in ("1", "true")

    # Текущий месяц для явки
    month_start = as_of.replace(day=1)
    if as_of.month == 12:
        month_end = _date(as_of.year + 1, 1, 1) - _timedelta(days=1)
    else:
        month_end = _date(as_of.year, as_of.month + 1, 1) - _timedelta(days=1)

    qs = OrganizationMembership.objects.filter(organization=org).select_related(
        "user", "compensation_plan",
    )
    if not include_inactive:
        qs = qs.filter(is_active=True)

    rows = []
    member_ids = []
    for m in qs:
        member_ids.append(m.id)
        bal = compute_balance(m, as_of)
        plan = getattr(m, "compensation_plan", None)

        # Явка за текущий месяц
        shifts = WorkShift.objects.filter(
            employee=m,
            shift_date__range=(month_start, min(month_end, as_of)),
            shift_index=0,
        ).values_list("kind", flat=True)
        attendance = {
            "work": 0, "overtime": 0, "vacation": 0,
            "sick_leave": 0, "absence": 0, "day_off": 0, "holiday": 0,
        }
        for k in shifts:
            attendance[k] = attendance.get(k, 0) + 1

        rows.append({
            "employee_id": str(m.id),
            "full_name": m.user.full_name if m.user_id else None,
            "position_title": m.position_title,
            "compensation_type": plan.compensation_type if plan else None,
            "accrued_total": str(bal.accrued_total),
            "paid_total": str(bal.paid_total),
            "adjustments_plus": str(bal.adjustments_plus),
            "adjustments_minus": str(bal.adjustments_minus),
            "balance_uzs": str(bal.balance_uzs),
            "is_active": m.is_active,
            "work_status": m.work_status,
            "attendance_month": attendance,
        })
    rows.sort(key=lambda r: float(r["balance_uzs"]), reverse=True)

    # ── Фонд ЗП по 12 месяцам ──────────────────────────────────────────
    monthly_fund = []
    today_ref = as_of
    for i in range(11, -1, -1):
        year = today_ref.year
        month = today_ref.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_start = _date(year, month, 1)
        if month == 12:
            m_end = _date(year + 1, 1, 1) - _timedelta(days=1)
        else:
            m_end = _date(year, month + 1, 1) - _timedelta(days=1)

        # Выплачено: PayrollPayout с payment.date в этом месяце, POSTED.
        paid_total = (
            PayrollPayout.objects.filter(
                organization=org,
                payment__status=Payment.Status.POSTED,
                payment__date__range=(m_start, m_end),
                employee_id__in=member_ids,
            ).aggregate(total=Sum("amount_uzs"))["total"] or _D("0")
        )
        # Начислено за месяц: суммируем accrue_for_period по всем активным
        # сотрудникам за этот месяц.
        # Чтобы не было O(emp × month) запросов в проде — это OK для текущего
        # масштаба (≤100 сотрудников × 12 мес = 1200 вызовов за запрос отчёта).
        accrued_total = _D("0")
        for m in qs:
            joined = m.joined_at.date() if m.joined_at else m_start
            start = max(m_start, joined)
            if start > m_end:
                continue
            res = accrue_for_period(m, start, m_end)
            accrued_total += res.accrued_uzs

        monthly_fund.append({
            "month": m_start.isoformat()[:7],
            "accrued_uzs": str(accrued_total),
            "paid_uzs": str(paid_total),
        })

    # ── Сводка явки по компании за текущий месяц ───────────────────────
    attendance_total = {
        "work": 0, "overtime": 0, "vacation": 0,
        "sick_leave": 0, "absence": 0, "day_off": 0, "holiday": 0,
    }
    for r in rows:
        for k, v in r["attendance_month"].items():
            attendance_total[k] = attendance_total.get(k, 0) + v

    totals = {
        "employees": len(rows),
        "total_balance_uzs": sum(float(r["balance_uzs"]) for r in rows),
        "total_paid_uzs": sum(float(r["paid_total"]) for r in rows),
        "total_accrued_uzs": sum(float(r["accrued_total"]) for r in rows),
        "attendance_month": attendance_total,
        "month_label": month_start.isoformat()[:7],
    }
    return Response({
        "as_of": as_of,
        "totals": totals,
        "rows": rows,
        "monthly_fund": monthly_fund,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_balance(request, pk):
    """GET /api/payroll/employees/<uuid:pk>/balance/?as_of=YYYY-MM-DD"""
    org, membership = _resolve_org_membership(request)
    employee = _employee_or_404(org, pk)
    _require_hr_or_self(membership, employee)
    as_of_str = request.query_params.get("as_of")
    if as_of_str:
        as_of = _parse_date(as_of_str, "as_of")
    else:
        from datetime import date as _date
        as_of = _date.today()

    bal = compute_balance(employee, as_of)
    return Response({
        "employee_id": bal.employee_id,
        "as_of": bal.as_of,
        "accrued_total": str(bal.accrued_total),
        "paid_total": str(bal.paid_total),
        "adjustments_plus": str(bal.adjustments_plus),
        "adjustments_minus": str(bal.adjustments_minus),
        "balance_uzs": str(bal.balance_uzs),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_accrued(request, pk):
    """GET /api/payroll/employees/<uuid:pk>/accrued/?from=YYYY-MM-DD&to=YYYY-MM-DD"""
    org, membership = _resolve_org_membership(request)
    employee = _employee_or_404(org, pk)
    _require_hr_or_self(membership, employee)
    from_d = _parse_date(request.query_params.get("from"), "from")
    to_d = _parse_date(request.query_params.get("to"), "to")

    res = accrue_for_period(employee, from_d, to_d)
    return Response({
        "employee_id": res.employee_id,
        "period_from": res.period_from,
        "period_to": res.period_to,
        "compensation_type": res.compensation_type,
        "currency_code": res.currency_code,
        "accrued_uzs": str(res.accrued_uzs),
        "breakdown": [
            {
                "date": ln.date,
                "rate_amount": str(ln.rate_amount),
                "rate_currency": ln.rate_currency,
                "accrued_native": str(ln.accrued_native),
                "accrued": str(ln.accrued),
                "exchange_rate": str(ln.exchange_rate),
                "note": ln.note,
            }
            for ln in res.breakdown
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_payroll(request):
    """
    GET /api/payroll/me/ — self-service: ставки, выплаты, корректировки, баланс.
    Не требует hr:r. Возвращает данные membership текущего юзера в активной org.
    """
    from datetime import date as _date

    from .models import PayrollAdjustment, PayrollPayout, SalaryRate

    org, membership = _resolve_org_membership(request)
    bal = compute_balance(membership, _date.today())
    rates = SalaryRate.objects.filter(employee=membership).order_by("-effective_from")[:50]
    payouts = (
        PayrollPayout.objects.filter(employee=membership)
        .select_related("payment").order_by("-period_to")[:100]
    )
    adjustments = (
        PayrollAdjustment.objects.filter(employee=membership)
        .order_by("-effective_date")[:100]
    )
    return Response({
        "balance": {
            "as_of": bal.as_of,
            "accrued_total": str(bal.accrued_total),
            "paid_total": str(bal.paid_total),
            "adjustments_plus": str(bal.adjustments_plus),
            "adjustments_minus": str(bal.adjustments_minus),
            "balance_uzs": str(bal.balance_uzs),
        },
        "rates": [
            {
                "id": str(r.id),
                "amount": str(r.amount),
                "currency_code": r.currency.code if r.currency_id else None,
                "effective_from": r.effective_from,
                "effective_to": r.effective_to,
                "reason": r.reason,
            }
            for r in rates
        ],
        "payouts": [
            {
                "id": str(p.id),
                "type": p.type,
                "amount_uzs": str(p.amount_uzs),
                "period_from": p.period_from,
                "period_to": p.period_to,
                "payment_doc_number": p.payment.doc_number if p.payment_id else None,
                "payment_status": p.payment.status if p.payment_id else None,
            }
            for p in payouts
        ],
        "adjustments": [
            {
                "id": str(a.id),
                "kind": a.kind,
                "effective_date": a.effective_date,
                "amount_uzs": str(a.amount_uzs),
                "reason": a.reason,
            }
            for a in adjustments
        ],
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def employee_calendar(request, pk):
    """
    GET /api/payroll/employees/<uuid:pk>/calendar/?from=YYYY-MM-DD&to=YYYY-MM-DD

    Возвращает объединённый календарь:
      - expected[] — ожидаемые смены из активного шаблона на каждую дату
      - actual[]   — фактические WorkShift в интервале
    """
    org, membership = _resolve_org_membership(request)
    employee = _employee_or_404(org, pk)
    _require_hr_or_self(membership, employee)
    from_d = _parse_date(request.query_params.get("from"), "from")
    to_d = _parse_date(request.query_params.get("to"), "to")
    if to_d < from_d:
        raise DRFValidationError({"to": "to раньше from."})

    template = template_for_employee_on(employee, from_d)
    expected = expand_template(template, from_d, to_d) if template else []
    actual_qs = WorkShift.objects.filter(
        employee=employee, shift_date__range=(from_d, to_d),
    ).order_by("shift_date")

    return Response({
        "employee_id": str(employee.id),
        "from": from_d,
        "to": to_d,
        "template_code": template.code if template else None,
        "expected": [
            {
                "date": e.date,
                "start_time": e.start_time.strftime("%H:%M") if e.start_time else None,
                "end_time": e.end_time.strftime("%H:%M") if e.end_time else None,
                "duration_hours": str(e.duration_hours),
                "kind": e.kind,
            }
            for e in expected
        ],
        "actual": [
            {
                "id": str(s.id),
                "date": s.shift_date,
                "kind": s.kind,
                "source": s.source,
                "start_at": s.start_at,
                "end_at": s.end_at,
                "hours": str(s.hours) if s.hours is not None else None,
                "notes": s.notes,
            }
            for s in actual_qs
        ],
    })
