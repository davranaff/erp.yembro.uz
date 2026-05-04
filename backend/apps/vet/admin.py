from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from .models import (
    VaccinationSchedule,
    VaccinationScheduleItem,
    VetDrug,
    VetStockBatch,
    VetTreatmentLog,
)


class ExpiringSoonFilter(admin.SimpleListFilter):
    title = "Срок годности"
    parameter_name = "expiring"

    def lookups(self, request, model_admin):
        return (
            ("30", "≤30 дней"),
            ("7", "≤7 дней"),
            ("expired", "Просрочено"),
        )

    def queryset(self, request, queryset):
        today = timezone.now().date()
        if self.value() == "30":
            return queryset.filter(
                expiration_date__lte=today + timedelta(days=30),
                expiration_date__gte=today,
            )
        if self.value() == "7":
            return queryset.filter(
                expiration_date__lte=today + timedelta(days=7),
                expiration_date__gte=today,
            )
        if self.value() == "expired":
            return queryset.filter(expiration_date__lt=today)
        return queryset


@admin.register(VetDrug)
class VetDrugAdmin(admin.ModelAdmin):
    list_display = (
        "nomenclature",
        "drug_type",
        "administration_route",
        "default_withdrawal_days",
        "is_active",
        "organization",
    )
    list_filter = ("organization", "drug_type", "administration_route", "is_active")
    search_fields = ("nomenclature__sku", "nomenclature__name", "notes")
    autocomplete_fields = ("organization", "module", "nomenclature", "created_by")


@admin.register(VetStockBatch)
class VetStockBatchAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "drug",
        "lot_number",
        "warehouse",
        "received_date",
        "expiration_date",
        "current_quantity",
        "status",
        "organization",
    )
    list_filter = (
        "organization",
        "status",
        "drug__drug_type",
        ExpiringSoonFilter,
    )
    date_hierarchy = "expiration_date"
    search_fields = (
        "doc_number",
        "lot_number",
        "drug__nomenclature__sku",
    )
    autocomplete_fields = (
        "organization",
        "module",
        "drug",
        "warehouse",
        "supplier",
        "purchase",
        "unit",
        "created_by",
    )


class VaccinationScheduleItemInline(admin.TabularInline):
    model = VaccinationScheduleItem
    extra = 0
    autocomplete_fields = ("drug",)
    fields = (
        "day_of_age",
        "drug",
        "dose_per_head",
        "administration_route",
        "is_mandatory",
        "notes",
    )


@admin.register(VaccinationSchedule)
class VaccinationScheduleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "direction", "is_active", "organization")
    list_filter = ("organization", "direction", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization", "created_by")
    inlines = [VaccinationScheduleItemInline]


@admin.register(VaccinationScheduleItem)
class VaccinationScheduleItemAdmin(admin.ModelAdmin):
    list_display = (
        "schedule",
        "day_of_age",
        "drug",
        "dose_per_head",
        "is_mandatory",
    )
    list_filter = ("schedule__direction", "is_mandatory")
    search_fields = (
        "schedule__code",
        "schedule__name",
        "drug__nomenclature__sku",
    )
    autocomplete_fields = ("schedule", "drug")


@admin.register(VetTreatmentLog)
class VetTreatmentLogAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "treatment_date",
        "target_block",
        "target_batch",
        "target_herd",
        "drug",
        "dose_quantity",
        "withdrawal_period_days",
        "veterinarian",
        "indication",
    )
    list_filter = (
        "organization",
        "indication",
        "drug__drug_type",
        "treatment_date",
    )
    date_hierarchy = "treatment_date"
    search_fields = (
        "doc_number",
        "drug__nomenclature__sku",
        "target_batch__doc_number",
        "target_herd__doc_number",
    )
    autocomplete_fields = (
        "organization",
        "module",
        "target_block",
        "target_batch",
        "target_herd",
        "drug",
        "stock_batch",
        "unit",
        "veterinarian",
        "technician",
        "schedule_item",
        "created_by",
    )
