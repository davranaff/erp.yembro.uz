from django.contrib import admin

from .models import (
    BreedingFeedConsumption,
    BreedingHerd,
    BreedingMortality,
    DailyEggProduction,
)


class DailyEggProductionInline(admin.TabularInline):
    model = DailyEggProduction
    extra = 0
    autocomplete_fields = ("outgoing_batch",)
    fields = ("date", "eggs_collected", "unfit_eggs", "outgoing_batch", "notes")


class BreedingMortalityInline(admin.TabularInline):
    model = BreedingMortality
    extra = 0
    fields = ("date", "dead_count", "cause", "recorded_by", "notes")


class BreedingFeedConsumptionInline(admin.TabularInline):
    model = BreedingFeedConsumption
    extra = 0
    autocomplete_fields = ("feed_batch",)
    fields = ("date", "feed_batch", "quantity_kg", "per_head_g", "notes")


@admin.register(BreedingHerd)
class BreedingHerdAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "block",
        "direction",
        "status",
        "initial_heads",
        "current_heads",
        "placed_at",
    )
    list_filter = ("organization", "status", "direction")
    date_hierarchy = "placed_at"
    search_fields = ("doc_number", "notes")
    autocomplete_fields = (
        "organization",
        "module",
        "block",
        "source_counterparty",
        "source_batch",
        "technologist",
    )
    inlines = [
        DailyEggProductionInline,
        BreedingMortalityInline,
        BreedingFeedConsumptionInline,
    ]


@admin.register(DailyEggProduction)
class DailyEggProductionAdmin(admin.ModelAdmin):
    list_display = ("herd", "date", "eggs_collected", "unfit_eggs", "outgoing_batch")
    list_filter = ("date",)
    date_hierarchy = "date"
    search_fields = ("herd__doc_number",)
    autocomplete_fields = ("herd", "outgoing_batch")


@admin.register(BreedingMortality)
class BreedingMortalityAdmin(admin.ModelAdmin):
    list_display = ("herd", "date", "dead_count", "cause")
    list_filter = ("date",)
    date_hierarchy = "date"
    search_fields = ("herd__doc_number", "cause")
    autocomplete_fields = ("herd", "recorded_by")


@admin.register(BreedingFeedConsumption)
class BreedingFeedConsumptionAdmin(admin.ModelAdmin):
    list_display = ("herd", "date", "feed_batch", "quantity_kg", "per_head_g")
    list_filter = ("date",)
    date_hierarchy = "date"
    search_fields = ("herd__doc_number",)
    autocomplete_fields = ("herd", "feed_batch")
