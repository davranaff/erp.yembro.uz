from __future__ import annotations

from datetime import date
from decimal import Decimal

from rest_framework import serializers

from apps.currency.models import Currency

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
from .services.schedule import validate_pattern


class PayrollPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollPeriod
        fields = (
            "id",
            "organization",
            "period_from",
            "period_to",
            "status",
            "closed_at",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "closed_at",
            "created_at",
            "updated_at",
        )


class HolidaySerializer(serializers.ModelSerializer):
    is_global = serializers.SerializerMethodField()

    class Meta:
        model = Holiday
        fields = (
            "id",
            "organization",
            "date",
            "name",
            "is_paid",
            "is_global",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "is_global",
            "created_at",
            "updated_at",
        )

    def get_is_global(self, obj):
        return obj.organization_id is None


class CompensationPlanSerializer(serializers.ModelSerializer):
    employee_full_name = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()

    class Meta:
        model = CompensationPlan
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "compensation_type",
            "currency",
            "currency_code",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "employee_full_name",
            "currency_code",
            "created_at",
            "updated_at",
        )

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None


class SalaryRateSerializer(serializers.ModelSerializer):
    employee_full_name = serializers.SerializerMethodField()
    currency_code = serializers.SerializerMethodField()

    class Meta:
        model = SalaryRate
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "amount",
            "currency",
            "currency_code",
            "effective_from",
            "effective_to",
            "reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "employee_full_name",
            "currency_code",
            "effective_to",  # закрывается сервисом set_rate
            "created_at",
            "updated_at",
        )

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None

    def get_currency_code(self, obj):
        return obj.currency.code if obj.currency_id else None

    def validate_amount(self, value):
        if value is None or value <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля.")
        return value


class WorkScheduleTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkScheduleTemplate
        fields = (
            "id",
            "organization",
            "code",
            "name",
            "pattern_kind",
            "pattern",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "organization", "created_at", "updated_at")

    def validate(self, attrs):
        kind = attrs.get("pattern_kind") or getattr(self.instance, "pattern_kind", None)
        pattern = attrs.get("pattern", getattr(self.instance, "pattern", None))
        if kind and pattern is not None:
            validate_pattern(kind, pattern)
        return attrs


class WorkScheduleSerializer(serializers.ModelSerializer):
    template_code = serializers.SerializerMethodField()
    employee_full_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkSchedule
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "template",
            "template_code",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "template_code",
            "employee_full_name",
            "created_at",
            "updated_at",
        )

    def get_template_code(self, obj):
        return obj.template.code if obj.template_id else None

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None


class WorkShiftSerializer(serializers.ModelSerializer):
    employee_full_name = serializers.SerializerMethodField()
    template_code = serializers.SerializerMethodField()

    class Meta:
        model = WorkShift
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "shift_date",
            "kind",
            "source",
            "start_at",
            "end_at",
            "hours",
            "source_template",
            "template_code",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "employee_full_name",
            "template_code",
            "created_at",
            "updated_at",
        )

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None

    def get_template_code(self, obj):
        return obj.source_template.code if obj.source_template_id else None


class PayrollPayoutSerializer(serializers.ModelSerializer):
    employee_full_name = serializers.SerializerMethodField()
    payment_doc_number = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = PayrollPayout
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "type",
            "period_from",
            "period_to",
            "payment",
            "payment_doc_number",
            "payment_status",
            "amount_uzs",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "employee_full_name",
            "payment",
            "payment_doc_number",
            "payment_status",
            "created_at",
            "updated_at",
        )

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None

    def get_payment_doc_number(self, obj):
        return obj.payment.doc_number if obj.payment_id else None

    def get_payment_status(self, obj):
        return obj.payment.status if obj.payment_id else None


class PayrollRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayrollRun
        fields = (
            "id",
            "organization",
            "period_from",
            "period_to",
            "payout_type",
            "cash_subaccount",
            "status",
            "employees_count",
            "total_amount_uzs",
            "notes",
            "executed_at",
            "created_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "status",
            "employees_count",
            "total_amount_uzs",
            "executed_at",
            "created_at",
        )


class PayrollRunPreviewSerializer(serializers.Serializer):
    period_from = serializers.DateField()
    period_to = serializers.DateField()


class PayrollRunExecuteSerializer(serializers.Serializer):
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    cash_subaccount = serializers.UUIDField()
    payout_type = serializers.ChoiceField(
        choices=PayrollPayout.Type.choices,
        default=PayrollPayout.Type.SALARY,
    )
    # Опционально: явные суммы по каждому сотруднику {emp_id: amount}.
    # Если не задано — берётся весь положительный balance каждого.
    employee_amounts = serializers.DictField(
        child=serializers.DecimalField(max_digits=18, decimal_places=2),
        required=False,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class PayrollAdjustmentSerializer(serializers.ModelSerializer):
    employee_full_name = serializers.SerializerMethodField()

    class Meta:
        model = PayrollAdjustment
        fields = (
            "id",
            "organization",
            "employee",
            "employee_full_name",
            "kind",
            "effective_date",
            "amount_uzs",
            "reason",
            "notes",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "organization",
            "employee_full_name",
            "created_at",
            "updated_at",
        )

    def get_employee_full_name(self, obj):
        return obj.employee.user.full_name if obj.employee_id else None

    def validate_amount_uzs(self, v):
        if v is None or v <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля.")
        return v


class PayoutCreateSerializer(serializers.Serializer):
    """Инпут для POST /api/payroll/payouts/ — создаёт Payment+PayrollPayout."""

    employee = serializers.UUIDField()
    type = serializers.ChoiceField(choices=PayrollPayout.Type.choices)
    amount_uzs = serializers.DecimalField(max_digits=18, decimal_places=2)
    period_from = serializers.DateField()
    period_to = serializers.DateField()
    cash_subaccount = serializers.UUIDField()
    on_date = serializers.DateField(required=False)
    channel = serializers.ChoiceField(
        choices=[
            ("cash", "Наличные"),
            ("transfer", "Перечисление"),
            ("click", "Click"),
            ("other", "Прочее"),
        ],
        default="cash",
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    # FX (опционально). Все три должны быть либо все заданы, либо все пусты.
    currency = serializers.UUIDField(required=False, allow_null=True)
    exchange_rate = serializers.DecimalField(
        max_digits=18, decimal_places=6, required=False, allow_null=True,
    )
    amount_foreign = serializers.DecimalField(
        max_digits=18, decimal_places=2, required=False, allow_null=True,
    )

    def validate_amount_uzs(self, v):
        if v is None or v <= 0:
            raise serializers.ValidationError("Сумма должна быть больше нуля.")
        return v

    def validate(self, attrs):
        if attrs["period_to"] < attrs["period_from"]:
            raise serializers.ValidationError(
                {"period_to": "period_to раньше period_from."}
            )
        fx_set = sum(
            1 for k in ("currency", "exchange_rate", "amount_foreign")
            if attrs.get(k) is not None
        )
        if fx_set not in (0, 3):
            raise serializers.ValidationError({
                "currency": "Для валютной выплаты задайте все три FX-поля.",
            })
        return attrs


class TemplatePreviewSerializer(serializers.Serializer):
    from_date = serializers.DateField()
    to_date = serializers.DateField()


class ApplyTemplateSerializer(serializers.Serializer):
    employee = serializers.UUIDField()
    template = serializers.UUIDField()
    from_date = serializers.DateField()
    to_date = serializers.DateField()


class TimesheetImportSerializer(serializers.Serializer):
    """
    Импорт табеля из CSV-text. Формат:
        email,date,kind,hours,notes
        worker@x.l,2026-05-15,work,8,
        worker@x.l,2026-05-16,vacation,,
    """
    csv_text = serializers.CharField()
    skip_existing = serializers.BooleanField(default=True)


class BulkSetKindSerializer(serializers.Serializer):
    """
    Массовое назначение kind смен на даты.
    `dates`: список ISO-дат YYYY-MM-DD.
    Существующие записи обновляются (kind, hours), новые создаются.
    """
    employee = serializers.UUIDField()
    dates = serializers.ListField(
        child=serializers.DateField(), allow_empty=False,
    )
    kind = serializers.ChoiceField(choices=WorkShift.Kind.choices)
    hours = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, allow_null=True,
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
