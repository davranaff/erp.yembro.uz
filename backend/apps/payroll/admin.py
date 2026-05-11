from django.contrib import admin

from .models import (
    CompensationPlan,
    PayrollAdjustment,
    PayrollPayout,
    SalaryRate,
    WorkSchedule,
    WorkScheduleTemplate,
    WorkShift,
)


@admin.register(PayrollAdjustment)
class PayrollAdjustmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "kind", "amount_uzs", "effective_date", "reason")
    list_filter = ("kind", "organization")
    raw_id_fields = ("employee",)
    date_hierarchy = "effective_date"


@admin.register(CompensationPlan)
class CompensationPlanAdmin(admin.ModelAdmin):
    list_display = ("employee", "compensation_type", "currency", "updated_at")
    list_filter = ("compensation_type", "organization")
    raw_id_fields = ("employee",)


@admin.register(SalaryRate)
class SalaryRateAdmin(admin.ModelAdmin):
    list_display = ("employee", "amount", "currency", "effective_from", "effective_to")
    list_filter = ("organization", "currency")
    raw_id_fields = ("employee",)
    date_hierarchy = "effective_from"


@admin.register(WorkScheduleTemplate)
class WorkScheduleTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "pattern_kind", "is_active", "organization")
    list_filter = ("pattern_kind", "is_active", "organization")
    search_fields = ("code", "name")


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ("employee", "template", "effective_from", "effective_to")
    list_filter = ("organization",)
    raw_id_fields = ("employee", "template")
    date_hierarchy = "effective_from"


@admin.register(WorkShift)
class WorkShiftAdmin(admin.ModelAdmin):
    list_display = ("employee", "shift_date", "kind", "source", "hours")
    list_filter = ("kind", "source", "organization")
    raw_id_fields = ("employee", "source_template")
    date_hierarchy = "shift_date"


@admin.register(PayrollPayout)
class PayrollPayoutAdmin(admin.ModelAdmin):
    list_display = ("employee", "type", "amount_uzs", "period_from", "period_to")
    list_filter = ("type", "organization")
    raw_id_fields = ("employee", "payment")
    date_hierarchy = "period_to"
