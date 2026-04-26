from django.contrib import admin

from .models import (
    SlaughterLabTest,
    SlaughterQualityCheck,
    SlaughterShift,
    SlaughterYield,
)


class SlaughterYieldInline(admin.TabularInline):
    model = SlaughterYield
    extra = 0
    autocomplete_fields = ("nomenclature", "unit", "output_batch")
    fields = (
        "nomenclature",
        "quantity",
        "unit",
        "share_percent",
        "output_batch",
        "notes",
    )


class SlaughterQualityCheckInline(admin.StackedInline):
    model = SlaughterQualityCheck
    max_num = 1
    can_delete = True
    autocomplete_fields = ("inspector",)
    fields = (
        "inspected_at",
        "inspector",
        "carcass_defect_percent",
        "trauma_percent",
        "cooling_temperature_c",
        "vet_inspection_passed",
        "notes",
    )


class SlaughterLabTestInline(admin.TabularInline):
    model = SlaughterLabTest
    extra = 0
    fields = (
        "indicator",
        "normal_range",
        "actual_value",
        "status",
        "sampled_at",
        "result_at",
        "operator",
    )


@admin.register(SlaughterShift)
class SlaughterShiftAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "line_block",
        "source_batch",
        "shift_date",
        "status",
        "live_heads_received",
        "live_weight_kg_total",
    )
    list_filter = ("organization", "status")
    date_hierarchy = "shift_date"
    search_fields = ("doc_number", "source_batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "line_block",
        "source_batch",
        "foreman",
    )
    inlines = [
        SlaughterYieldInline,
        SlaughterQualityCheckInline,
        SlaughterLabTestInline,
    ]


@admin.register(SlaughterYield)
class SlaughterYieldAdmin(admin.ModelAdmin):
    list_display = ("shift", "nomenclature", "quantity", "unit", "share_percent")
    search_fields = ("shift__doc_number", "nomenclature__sku")
    autocomplete_fields = ("shift", "nomenclature", "unit", "output_batch")


@admin.register(SlaughterQualityCheck)
class SlaughterQualityCheckAdmin(admin.ModelAdmin):
    list_display = (
        "shift",
        "inspected_at",
        "inspector",
        "vet_inspection_passed",
        "carcass_defect_percent",
    )
    search_fields = ("shift__doc_number",)
    autocomplete_fields = ("shift", "inspector")


@admin.register(SlaughterLabTest)
class SlaughterLabTestAdmin(admin.ModelAdmin):
    list_display = ("shift", "indicator", "status", "normal_range", "actual_value")
    list_filter = ("status",)
    search_fields = ("shift__doc_number", "indicator")
    autocomplete_fields = ("shift", "operator")
