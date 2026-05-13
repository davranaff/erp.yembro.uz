from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError as DRFValidationError
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.response import Response

from apps.accounting.models import GLSubaccount
from apps.common.viewsets import OrgScopedModelViewSet
from apps.organizations.models import OrganizationMembership

from .models import (
    CompensationPlan,
    Holiday,
    PayrollAdjustment,
    PayrollPayout,
    PayrollPeriod,
    PayrollRun,
    SalaryRate,
    WorkSchedule,
    WorkScheduleTemplate,
    WorkShift,
)
from .serializers import (
    ApplyTemplateSerializer,
    BulkSetKindSerializer,
    CompensationPlanSerializer,
    HolidaySerializer,
    PayoutCreateSerializer,
    PayrollAdjustmentSerializer,
    PayrollPayoutSerializer,
    PayrollPeriodSerializer,
    PayrollRunExecuteSerializer,
    PayrollRunPreviewSerializer,
    PayrollRunSerializer,
    SalaryRateSerializer,
    TemplatePreviewSerializer,
    TimesheetImportSerializer,
    WorkScheduleSerializer,
    WorkScheduleTemplateSerializer,
    WorkShiftSerializer,
)
from .services.payout import create_payout
from .services.rates import set_rate
from .services.schedule import apply_template_to_period, expand_template


class PayrollPeriodViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/periods/ — закрытые учётные периоды.
    POST → создаёт open-период.
    POST /{id}/close/ → закрывает (запрещает редактирование смен/корректировок).
    POST /{id}/reopen/ → открывает (только org-admin).
    """
    serializer_class = PayrollPeriodSerializer
    queryset = PayrollPeriod.objects.all()
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status"]
    ordering = ["-period_to"]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        from django.utils import timezone as _tz
        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log

        period = self.get_object()
        if period.status == PayrollPeriod.Status.CLOSED:
            return Response(self.get_serializer(period).data)
        period.status = PayrollPeriod.Status.CLOSED
        period.closed_at = _tz.now()
        period.closed_by = request.user
        period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
        audit_log(
            organization=period.organization,
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            entity=period,
            action_verb=f"close period {period.period_from}..{period.period_to}"[:64],
        )
        return Response(self.get_serializer(period).data)

    @action(detail=True, methods=["post"])
    def reopen(self, request, pk=None):
        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log
        from apps.common.permissions import is_org_admin

        membership = getattr(request, "membership", None)
        if membership is None or not is_org_admin(membership):
            raise DRFValidationError(
                {"detail": "Переоткрытие периода — только org-admin."}
            )
        period = self.get_object()
        period.status = PayrollPeriod.Status.OPEN
        period.closed_at = None
        period.closed_by = None
        period.save(update_fields=["status", "closed_at", "closed_by", "updated_at"])
        audit_log(
            organization=period.organization,
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            entity=period,
            action_verb=f"reopen period {period.period_from}..{period.period_to}"[:64],
        )
        return Response(self.get_serializer(period).data)


class HolidayViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/holidays/ — праздники.
    Список включает глобальные (organization=NULL) + текущей org.
    Создаются только организационные. Глобальные правятся через миграции/admin.
    """
    serializer_class = HolidaySerializer
    queryset = Holiday.objects.all()
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {"date": ["exact", "gte", "lte"]}
    ordering = ["date"]

    def get_queryset(self):
        # Override OrganizationScopedMixin: глобальные тоже видны.
        from django.db.models import Q
        org = getattr(self.request, "organization", None)
        if org is None:
            return Holiday.objects.none()
        return Holiday.objects.filter(
            Q(organization__isnull=True) | Q(organization=org)
        )

    def perform_destroy(self, instance):
        if instance.organization_id is None:
            raise DRFValidationError(
                {"detail": "Глобальные праздники нельзя удалить через API."}
            )
        super().perform_destroy(instance)


class CompensationPlanViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/compensation-plans/ — план оплаты сотрудника (OneToOne к Membership).
    При создании/изменении автоматически записывает CompensationPlanHistory.
    """
    serializer_class = CompensationPlanSerializer
    queryset = CompensationPlan.objects.select_related(
        "employee__user", "currency",
    )
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["employee", "compensation_type"]
    search_fields = ["employee__user__full_name", "employee__user__email"]
    ordering_fields = ["created_at", "compensation_type"]
    ordering = ["-created_at"]

    def perform_create(self, serializer):
        from datetime import date as _date

        from .services.compensation import change_compensation_type

        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        # Записываем в History (создаётся первая запись).
        change_compensation_type(
            employee=instance.employee,
            new_type=instance.compensation_type,
            effective_from=_date.today(),
            user=getattr(self.request, "user", None),
            reason="initial plan",
        )
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    def perform_update(self, serializer):
        from datetime import date as _date

        from .services.compensation import change_compensation_type

        old_type = serializer.instance.compensation_type if serializer.instance else None
        instance = serializer.save()
        # Если тип изменился — записываем в History.
        if old_type and old_type != instance.compensation_type:
            change_compensation_type(
                employee=instance.employee,
                new_type=instance.compensation_type,
                effective_from=_date.today(),
                user=getattr(self.request, "user", None),
                reason="type changed via API",
            )
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.UPDATE, instance)


class SalaryRateViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/rates/ — история ставок.
    POST → сервис set_rate (закрывает прошлую открытую запись).
    """
    serializer_class = SalaryRateSerializer
    queryset = SalaryRate.objects.select_related(
        "employee__user", "currency",
    )
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["employee", "currency"]
    ordering = ["-effective_from"]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def perform_create(self, serializer):
        data = serializer.validated_data
        employee = data["employee"]
        if employee.organization_id != self.request.organization.id:
            raise DRFValidationError({"employee": "Сотрудник из другой организации."})
        try:
            rate = set_rate(
                employee=employee,
                amount=data["amount"],
                currency=data["currency"],
                effective_from=data["effective_from"],
                user=self.request.user,
                reason=data.get("reason", "") or "",
            )
        except DjangoValidationError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        serializer.instance = rate

    def perform_destroy(self, instance):
        # Удаление допустимо только для последней open-ended записи (откат назначения).
        if instance.effective_to is not None:
            raise DRFValidationError(
                {"detail": "Удалить можно только последнюю активную ставку."}
            )
        super().perform_destroy(instance)


class WorkScheduleTemplateViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/schedule-templates/ — общесистемные шаблоны графиков.
    """
    serializer_class = WorkScheduleTemplateSerializer
    queryset = WorkScheduleTemplate.objects.all()
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["pattern_kind", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["code"]

    def perform_destroy(self, instance):
        """Запрет hard-delete если есть active assignments. Используйте is_active=False."""
        from .models import WorkSchedule

        active_count = WorkSchedule.objects.filter(
            template=instance, effective_to__isnull=True,
        ).count()
        if active_count > 0:
            raise DRFValidationError({
                "detail": (
                    f"Шаблон используется в {active_count} активных назначениях. "
                    "Сначала закройте назначения или архивируйте шаблон (is_active=False)."
                )
            })
        super().perform_destroy(instance)

    @action(detail=True, methods=["post"])
    def preview(self, request, pk=None):
        """POST /api/payroll/schedule-templates/{id}/preview/ — ожидаемые смены без сохранения."""
        template = self.get_object()
        ser = TemplatePreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        out = expand_template(
            template, ser.validated_data["from_date"], ser.validated_data["to_date"]
        )
        return Response([
            {
                "date": e.date,
                "start_time": e.start_time.strftime("%H:%M") if e.start_time else None,
                "end_time": e.end_time.strftime("%H:%M") if e.end_time else None,
                "duration_hours": str(e.duration_hours),
                "kind": e.kind,
            }
            for e in out
        ])


class WorkScheduleViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/work-schedules/ — назначения шаблонов на сотрудников.
    """
    serializer_class = WorkScheduleSerializer
    queryset = WorkSchedule.objects.select_related(
        "employee__user", "template",
    )
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["employee", "template"]
    ordering = ["-effective_from"]
    http_method_names = ["get", "post", "delete", "head", "options"]


class WorkShiftViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/work-shifts/ — табель.
    Auto-detect overtime: если hours > template.duration_hours и kind=work →
    автоматически меняется на OVERTIME.
    """
    serializer_class = WorkShiftSerializer
    queryset = WorkShift.objects.select_related(
        "employee__user", "source_template",
    )
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        "employee": ["exact"],
        "kind": ["exact"],
        "source": ["exact"],
        "shift_date": ["exact", "gte", "lte"],
    }
    ordering = ["-shift_date"]

    def _auto_overtime(self, instance: WorkShift) -> None:
        from .services.schedule import auto_detect_overtime
        if auto_detect_overtime(instance.employee, instance):
            instance.kind = WorkShift.Kind.OVERTIME
            instance.save(update_fields=["kind", "updated_at"])

    def perform_create(self, serializer):
        instance = serializer.save(**self._save_kwargs_for_create(serializer))
        self._auto_overtime(instance)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.CREATE, instance)

    def perform_update(self, serializer):
        instance = serializer.save()
        self._auto_overtime(instance)
        from apps.audit.models import AuditLog
        self._write_audit(AuditLog.Action.UPDATE, instance)

    @action(detail=False, methods=["post"], url_path="import-csv")
    def import_csv(self, request):
        """
        POST /api/payroll/work-shifts/import-csv/
        Body: {csv_text, skip_existing}.
        Формат CSV: email,date,kind,hours,notes (с заголовком).
        """
        import csv
        import io

        from django.db import transaction as _tx

        from apps.users.models import User

        ser = TimesheetImportSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = request.organization
        skip_existing = ser.validated_data.get("skip_existing", True)

        reader = csv.DictReader(io.StringIO(ser.validated_data["csv_text"]))
        valid_kinds = {k for k, _ in WorkShift.Kind.choices}

        created = updated = errors = 0
        error_lines: list[str] = []

        # Кэш membership по email
        memberships: dict[str, OrganizationMembership] = {}

        with _tx.atomic():
            for i, row in enumerate(reader, start=2):  # 2 — потому что header=1
                email = (row.get("email") or "").strip().lower()
                date_str = (row.get("date") or "").strip()
                kind = (row.get("kind") or "work").strip()
                hours = (row.get("hours") or "").strip()
                notes = (row.get("notes") or "").strip()
                if not email or not date_str:
                    errors += 1
                    error_lines.append(f"line {i}: empty email/date")
                    continue
                if kind not in valid_kinds:
                    errors += 1
                    error_lines.append(f"line {i}: unknown kind={kind}")
                    continue

                m = memberships.get(email)
                if m is None:
                    user = User.objects.filter(email__iexact=email).first()
                    if user is None:
                        errors += 1
                        error_lines.append(f"line {i}: user {email} not found")
                        continue
                    m = OrganizationMembership.objects.filter(
                        user=user, organization=org, is_active=True,
                    ).first()
                    if m is None:
                        errors += 1
                        error_lines.append(f"line {i}: {email} not employee of org")
                        continue
                    memberships[email] = m

                from datetime import datetime as _dt
                try:
                    shift_date = _dt.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    errors += 1
                    error_lines.append(f"line {i}: bad date={date_str}")
                    continue

                existing = WorkShift.objects.filter(
                    employee=m, shift_date=shift_date, shift_index=0,
                ).first()
                if existing and skip_existing:
                    continue
                hours_val = None
                if hours:
                    try:
                        hours_val = float(hours)
                    except ValueError:
                        pass

                if existing:
                    existing.kind = kind
                    existing.hours = hours_val
                    if notes:
                        existing.notes = notes
                    existing.source = WorkShift.Source.IMPORT
                    existing.save()
                    updated += 1
                else:
                    WorkShift.objects.create(
                        organization=org, employee=m,
                        shift_date=shift_date, kind=kind,
                        source=WorkShift.Source.IMPORT,
                        hours=hours_val, notes=notes,
                        created_by=request.user,
                    )
                    created += 1

        return Response({
            "created": created,
            "updated": updated,
            "errors": errors,
            "error_lines": error_lines[:50],
        })

    @action(detail=False, methods=["post"], url_path="bulk-set-kind")
    def bulk_set_kind(self, request):
        """
        POST /api/payroll/work-shifts/bulk-set-kind/
        Body: {employee, dates: [...], kind, hours?, notes?}.
        Создаёт новые WorkShift или обновляет существующие.
        """
        from django.db import transaction as _tx

        ser = BulkSetKindSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = request.organization
        try:
            employee = OrganizationMembership.objects.get(
                pk=ser.validated_data["employee"], organization=org,
            )
        except OrganizationMembership.DoesNotExist:
            raise NotFound({"employee": "Сотрудник не найден."})

        kind = ser.validated_data["kind"]
        dates = ser.validated_data["dates"]
        hours = ser.validated_data.get("hours")
        notes = ser.validated_data.get("notes", "") or ""
        existing = {
            (s.shift_date, s.shift_index): s
            for s in WorkShift.objects.filter(
                employee=employee, shift_date__in=dates, shift_index=0,
            )
        }
        created = updated = 0
        with _tx.atomic():
            for d in dates:
                key = (d, 0)
                if key in existing:
                    s = existing[key]
                    s.kind = kind
                    s.hours = hours
                    if notes:
                        s.notes = notes
                    s.source = WorkShift.Source.MANUAL
                    s.save()
                    updated += 1
                else:
                    WorkShift.objects.create(
                        organization=org,
                        employee=employee,
                        shift_date=d,
                        shift_index=0,
                        kind=kind,
                        source=WorkShift.Source.MANUAL,
                        hours=hours,
                        notes=notes,
                        created_by=request.user,
                    )
                    created += 1
        return Response({"created": created, "updated": updated})

    @action(detail=False, methods=["post"], url_path="bulk-clear")
    def bulk_clear(self, request):
        """
        POST /api/payroll/work-shifts/bulk-clear/
        Body: {employee, dates: [...]}.
        Удаляет WorkShift'ы на указанных датах. После этого даты «чистые» —
        для accrual они становятся обычными календарными днями (платятся
        как rate / days_in_month), пока HR явно не назначит другой kind.
        """
        from django.db import transaction as _tx

        ser = BulkSetKindSerializer(data={**request.data, "kind": WorkShift.Kind.WORK})
        # Используем тот же сериализатор для валидации employee/dates;
        # kind игнорируем (передан фиктивный, чтобы валидатор не ругался).
        ser.is_valid(raise_exception=True)
        org = request.organization
        try:
            employee = OrganizationMembership.objects.get(
                pk=ser.validated_data["employee"], organization=org,
            )
        except OrganizationMembership.DoesNotExist:
            raise NotFound({"employee": "Сотрудник не найден."})

        dates = ser.validated_data["dates"]
        with _tx.atomic():
            deleted, _details = WorkShift.objects.filter(
                employee=employee, shift_date__in=dates,
            ).delete()
        return Response({"deleted": deleted})

    @action(detail=False, methods=["post"], url_path="bulk")
    def bulk_apply_template(self, request):
        """
        POST /api/payroll/work-shifts/bulk/
        Body: {employee, template, from_date, to_date} — генерирует смены из шаблона.
        Не перезаписывает существующие.
        """
        ser = ApplyTemplateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = request.organization
        try:
            employee = OrganizationMembership.objects.get(
                pk=ser.validated_data["employee"], organization=org,
            )
            template = WorkScheduleTemplate.objects.get(
                pk=ser.validated_data["template"], organization=org,
            )
        except OrganizationMembership.DoesNotExist:
            raise NotFound({"employee": "Сотрудник не найден."})
        except WorkScheduleTemplate.DoesNotExist:
            raise NotFound({"template": "Шаблон не найден."})

        created = apply_template_to_period(
            employee=employee,
            template=template,
            from_date=ser.validated_data["from_date"],
            to_date=ser.validated_data["to_date"],
            user=request.user,
        )
        return Response({"created": created}, status=status.HTTP_201_CREATED)


class PayrollRunViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/runs/ — ведомости на выплату.

    GET — список выполненных запусков (read-only через CRUD).
    POST /preview/ — предпросмотр: список сотрудников с долгом на period_to.
    POST /execute/ — атомарно запускает массовую выплату.
    """
    serializer_class = PayrollRunSerializer
    queryset = PayrollRun.objects.all()
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ["status", "payout_type"]
    ordering = ["-period_to", "-created_at"]
    http_method_names = ["get", "post", "head", "options"]

    @action(detail=False, methods=["post"])
    def preview(self, request):
        """POST /api/payroll/runs/preview/ — список сотрудников с положительным балансом."""
        ser = PayrollRunPreviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        from .services.run import preview_run

        lines = preview_run(
            organization=request.organization,
            period_from=ser.validated_data["period_from"],
            period_to=ser.validated_data["period_to"],
        )
        return Response({
            "period_from": ser.validated_data["period_from"],
            "period_to": ser.validated_data["period_to"],
            "rows": [
                {
                    "employee_id": ln.employee_id,
                    "full_name": ln.full_name,
                    "balance_uzs": str(ln.balance_uzs),
                    "due_uzs": str(ln.due_uzs),
                }
                for ln in lines
            ],
            "total_uzs": str(sum(ln.due_uzs for ln in lines)),
        })

    @action(detail=False, methods=["post"])
    def execute(self, request):
        """POST /api/payroll/runs/execute/ — выполнить ведомость."""
        from apps.accounting.models import GLSubaccount

        ser = PayrollRunExecuteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        org = request.organization
        try:
            cash = GLSubaccount.objects.select_related("account").get(
                pk=ser.validated_data["cash_subaccount"],
                account__organization=org,
            )
        except GLSubaccount.DoesNotExist:
            raise NotFound({"cash_subaccount": "Касса не найдена."})

        from .services.run import execute_run

        try:
            run = execute_run(
                organization=org,
                period_from=ser.validated_data["period_from"],
                period_to=ser.validated_data["period_to"],
                cash_subaccount=cash,
                payout_type=ser.validated_data.get("payout_type", PayrollPayout.Type.SALARY),
                employee_amounts=ser.validated_data.get("employee_amounts"),
                notes=ser.validated_data.get("notes", ""),
                user=request.user,
            )
        except DjangoValidationError as exc:
            from rest_framework.exceptions import ValidationError as DRFErr
            raise DRFErr(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )

        out = PayrollRunSerializer(run, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)


class PayrollAdjustmentViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/adjustments/ — корректировки начислений (бонус/штраф/доначисление).
    Не создаёт Payment; учитывается в compute_balance.
    """
    serializer_class = PayrollAdjustmentSerializer
    queryset = PayrollAdjustment.objects.select_related("employee__user")
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        "employee": ["exact"],
        "kind": ["exact"],
        "effective_date": ["exact", "gte", "lte"],
    }
    ordering = ["-effective_date"]


class PayrollPayoutViewSet(OrgScopedModelViewSet):
    """
    /api/payroll/payouts/ — выплаты ЗП.
    POST использует PayoutCreateSerializer и сервис create_payout.
    """
    queryset = PayrollPayout.objects.select_related(
        "employee__user", "payment",
    )
    module_code = "hr"
    required_level = "r"
    write_level = "rw"
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = {
        "employee": ["exact"],
        "type": ["exact"],
        "period_from": ["gte", "lte"],
        "period_to": ["gte", "lte"],
    }
    ordering = ["-period_to", "-created_at"]
    http_method_names = ["get", "post", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return PayoutCreateSerializer
        return PayrollPayoutSerializer

    def perform_create(self, serializer):
        from apps.currency.models import Currency
        data = serializer.validated_data
        org = self.request.organization
        try:
            employee = OrganizationMembership.objects.get(
                pk=data["employee"], organization=org,
            )
        except OrganizationMembership.DoesNotExist:
            raise NotFound({"employee": "Сотрудник не найден."})
        try:
            cash_sub = GLSubaccount.objects.select_related("account").get(
                pk=data["cash_subaccount"], account__organization=org,
            )
        except GLSubaccount.DoesNotExist:
            raise NotFound({"cash_subaccount": "Касса не найдена."})

        currency = None
        if data.get("currency"):
            try:
                currency = Currency.objects.get(pk=data["currency"])
            except Currency.DoesNotExist:
                raise NotFound({"currency": "Валюта не найдена."})

        payout = create_payout(
            employee=employee,
            type=data["type"],
            amount_uzs=data["amount_uzs"],
            period_from=data["period_from"],
            period_to=data["period_to"],
            cash_subaccount=cash_sub,
            on_date=data.get("on_date"),
            channel=data.get("channel", "cash"),
            notes=data.get("notes", "") or "",
            user=self.request.user,
            currency=currency,
            exchange_rate=data.get("exchange_rate"),
            amount_foreign=data.get("amount_foreign"),
        )
        serializer.instance = payout

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = PayrollPayoutSerializer(serializer.instance, context=self.get_serializer_context())
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        POST /api/payroll/payouts/{id}/cancel/ — отменить выплату.

        Body (опц.): {"reason": "..."}

        Сторнирует Payment через reverse_payment (создаётся reverse JE),
        Payment переходит в CANCELLED. PayrollPayout НЕ удаляется — остаётся
        для аудита, но при compute_balance его выплата исключается через
        фильтр payment.status=POSTED.
        """
        from apps.payments.services.reverse import (
            PaymentReverseError,
            reverse_payment,
        )
        from apps.audit.models import AuditLog
        from apps.audit.services.writer import audit_log

        # Только org-admin может отменить выплату.
        from apps.common.permissions import is_org_admin
        membership = getattr(request, "membership", None)
        if membership is None or not is_org_admin(membership):
            raise DRFValidationError(
                {"detail": "Отмена выплаты — только для admin."}
            )

        payout = self.get_object()
        reason = (request.data.get("reason") or "").strip() or "cancel payout"
        try:
            reverse_payment(payout.payment, reason=reason, user=request.user)
        except PaymentReverseError as exc:
            raise DRFValidationError(
                exc.message_dict if hasattr(exc, "message_dict") else exc.messages
            )
        audit_log(
            organization=payout.organization,
            actor=request.user,
            action=AuditLog.Action.UPDATE,
            entity=payout,
            action_verb=f"cancel payout {payout.id} · {reason[:40]}"[:64],
        )
        payout.refresh_from_db()
        out = PayrollPayoutSerializer(payout, context=self.get_serializer_context())
        return Response(out.data)
