from django.contrib import admin

from .models import IncubationRegimeDay, IncubationRun, MirageInspection


class IncubationRegimeDayInline(admin.TabularInline):
    model = IncubationRegimeDay
    extra = 0
    fields = (
        "day",
        "temperature_c",
        "humidity_percent",
        "egg_turns_per_day",
        "actual_temperature_c",
        "actual_humidity_percent",
        "observed_at",
        "observed_by",
    )


class MirageInspectionInline(admin.TabularInline):
    model = MirageInspection
    extra = 0
    autocomplete_fields = ("inspector",)
    fields = (
        "inspection_date",
        "day_of_incubation",
        "inspected_count",
        "fertile_count",
        "discarded_count",
        "inspector",
        "notes",
    )


@admin.register(IncubationRun)
class IncubationRunAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "incubator_block",
        "hatcher_block",
        "batch",
        "loaded_date",
        "expected_hatch_date",
        "status",
        "eggs_loaded",
        "hatched_count",
    )
    list_filter = ("organization", "status")
    date_hierarchy = "loaded_date"
    search_fields = ("doc_number", "batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "incubator_block",
        "hatcher_block",
        "batch",
        "technologist",
    )
    inlines = [IncubationRegimeDayInline, MirageInspectionInline]


@admin.register(IncubationRegimeDay)
class IncubationRegimeDayAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "day",
        "temperature_c",
        "humidity_percent",
        "actual_temperature_c",
        "actual_humidity_percent",
    )
    search_fields = ("run__doc_number",)
    autocomplete_fields = ("run", "observed_by")


@admin.register(MirageInspection)
class MirageInspectionAdmin(admin.ModelAdmin):
    list_display = (
        "run",
        "inspection_date",
        "day_of_incubation",
        "inspected_count",
        "fertile_count",
        "discarded_count",
    )
    list_filter = ("inspection_date",)
    date_hierarchy = "inspection_date"
    search_fields = ("run__doc_number",)
    autocomplete_fields = ("run", "inspector")
