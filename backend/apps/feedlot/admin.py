from django.contrib import admin

from .models import (
    DailyWeighing,
    FeedlotBatch,
    FeedlotFeedConsumption,
    FeedlotMortality,
)


class DailyWeighingInline(admin.TabularInline):
    model = DailyWeighing
    extra = 0
    fields = (
        "date",
        "day_of_age",
        "sample_size",
        "avg_weight_kg",
        "gain_kg",
        "operator",
    )


class FeedlotFeedConsumptionInline(admin.TabularInline):
    model = FeedlotFeedConsumption
    extra = 0
    autocomplete_fields = ("feed_batch",)
    fields = (
        "period_from_day",
        "period_to_day",
        "feed_type",
        "feed_batch",
        "total_kg",
        "per_head_g",
        "period_fcr",
    )


class FeedlotMortalityInline(admin.TabularInline):
    model = FeedlotMortality
    extra = 0
    fields = ("date", "day_of_age", "dead_count", "cause", "recorded_by")


@admin.register(FeedlotBatch)
class FeedlotBatchAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "house_block",
        "batch",
        "placed_date",
        "status",
        "initial_heads",
        "current_heads",
        "target_weight_kg",
    )
    list_filter = ("organization", "status")
    date_hierarchy = "placed_date"
    search_fields = ("doc_number", "batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "house_block",
        "batch",
        "technologist",
    )
    inlines = [
        DailyWeighingInline,
        FeedlotFeedConsumptionInline,
        FeedlotMortalityInline,
    ]


@admin.register(DailyWeighing)
class DailyWeighingAdmin(admin.ModelAdmin):
    list_display = (
        "feedlot_batch",
        "day_of_age",
        "date",
        "sample_size",
        "avg_weight_kg",
        "gain_kg",
    )
    list_filter = ("date",)
    search_fields = ("feedlot_batch__doc_number",)
    autocomplete_fields = ("feedlot_batch", "operator")


@admin.register(FeedlotFeedConsumption)
class FeedlotFeedConsumptionAdmin(admin.ModelAdmin):
    list_display = (
        "feedlot_batch",
        "period_from_day",
        "period_to_day",
        "feed_type",
        "feed_batch",
        "total_kg",
        "period_fcr",
    )
    list_filter = ("feed_type",)
    search_fields = ("feedlot_batch__doc_number",)
    autocomplete_fields = ("feedlot_batch", "feed_batch")


@admin.register(FeedlotMortality)
class FeedlotMortalityAdmin(admin.ModelAdmin):
    list_display = ("feedlot_batch", "date", "day_of_age", "dead_count", "cause")
    list_filter = ("date",)
    date_hierarchy = "date"
    search_fields = ("feedlot_batch__doc_number", "cause")
    autocomplete_fields = ("feedlot_batch", "recorded_by")
