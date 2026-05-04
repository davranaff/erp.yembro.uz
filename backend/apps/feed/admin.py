from django.contrib import admin

from .models import (
    FeedBatch,
    FeedConsumptionPlan,
    FeedLotShrinkageState,
    FeedShrinkageProfile,
    LabResult,
    NomenclatureNutritionProfile,
    ProductionTask,
    ProductionTaskComponent,
    RawMaterialBatch,
    Recipe,
    RecipeComponent,
    RecipeVersion,
)


class RecipeComponentInline(admin.TabularInline):
    model = RecipeComponent
    extra = 0
    autocomplete_fields = ("nomenclature", "vet_drug")
    fields = (
        "nomenclature",
        "share_percent",
        "min_share_percent",
        "max_share_percent",
        "is_medicated",
        "withdrawal_period_days",
        "vet_drug",
        "sort_order",
    )


class RecipeVersionInline(admin.TabularInline):
    model = RecipeVersion
    extra = 0
    fields = ("version_number", "status", "effective_from", "author")
    readonly_fields = ("version_number",)
    show_change_link = True


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "organization",
        "direction",
        "is_medicated",
        "is_active",
    )
    list_filter = ("organization", "direction", "is_medicated", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization", "created_by")
    inlines = [RecipeVersionInline]


@admin.register(RecipeVersion)
class RecipeVersionAdmin(admin.ModelAdmin):
    list_display = (
        "recipe",
        "version_number",
        "status",
        "effective_from",
        "author",
    )
    list_filter = ("status", "recipe__direction")
    search_fields = ("recipe__code", "recipe__name")
    autocomplete_fields = ("recipe", "author")
    inlines = [RecipeComponentInline]


@admin.register(NomenclatureNutritionProfile)
class NomenclatureNutritionProfileAdmin(admin.ModelAdmin):
    list_display = (
        "nomenclature",
        "protein_percent",
        "fat_percent",
        "fibre_percent",
        "me_kcal_per_kg",
    )
    search_fields = ("nomenclature__sku", "nomenclature__name")
    autocomplete_fields = ("nomenclature",)


@admin.register(RawMaterialBatch)
class RawMaterialBatchAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "nomenclature",
        "supplier",
        "warehouse",
        "received_date",
        "quantity",
        "current_quantity",
        "status",
        "quarantine_until",
    )
    list_filter = ("organization", "status", "received_date")
    date_hierarchy = "received_date"
    search_fields = ("doc_number", "nomenclature__sku", "supplier__name")
    autocomplete_fields = (
        "organization",
        "module",
        "nomenclature",
        "supplier",
        "purchase",
        "warehouse",
        "unit",
    )


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "status",
        "subject_content_type",
        "subject_object_id",
        "sampled_at",
        "protein_percent",
        "operator",
    )
    list_filter = ("organization", "status", "subject_content_type")
    date_hierarchy = "sampled_at"
    search_fields = ("doc_number",)
    autocomplete_fields = ("organization", "operator", "approver")


class ProductionTaskComponentInline(admin.TabularInline):
    model = ProductionTaskComponent
    extra = 0
    autocomplete_fields = ("nomenclature", "source_batch", "lab_result_snapshot")
    fields = (
        "nomenclature",
        "source_batch",
        "planned_quantity",
        "actual_quantity",
        "planned_price_per_unit_uzs",
        "actual_price_per_unit_uzs",
        "lab_result_snapshot",
        "sort_order",
    )


@admin.register(ProductionTask)
class ProductionTaskAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "recipe_version",
        "production_line",
        "shift",
        "scheduled_at",
        "status",
        "planned_quantity_kg",
        "actual_quantity_kg",
        "is_medicated",
    )
    list_filter = ("organization", "status", "shift", "is_medicated")
    date_hierarchy = "scheduled_at"
    search_fields = ("doc_number",)
    autocomplete_fields = (
        "organization",
        "module",
        "recipe_version",
        "production_line",
        "operator",
        "technologist",
    )
    inlines = [ProductionTaskComponentInline]


@admin.register(FeedBatch)
class FeedBatchAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "recipe_version",
        "produced_at",
        "quantity_kg",
        "current_quantity_kg",
        "unit_cost_uzs",
        "status",
        "quality_passport_status",
        "is_medicated",
        "withdrawal_period_ends",
        "storage_bin",
    )
    list_filter = (
        "organization",
        "status",
        "quality_passport_status",
        "is_medicated",
    )
    date_hierarchy = "produced_at"
    search_fields = ("doc_number",)
    autocomplete_fields = (
        "organization",
        "module",
        "produced_by_task",
        "recipe_version",
        "storage_bin",
        "storage_warehouse",
    )


@admin.register(FeedShrinkageProfile)
class FeedShrinkageProfileAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "target_type",
        "nomenclature",
        "recipe",
        "warehouse",
        "period_days",
        "percent_per_period",
        "max_total_percent",
        "is_active",
    )
    list_filter = ("organization", "target_type", "is_active")
    search_fields = ("nomenclature__sku", "recipe__code", "note")
    autocomplete_fields = ("organization", "nomenclature", "recipe", "warehouse")


@admin.register(FeedLotShrinkageState)
class FeedLotShrinkageStateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "organization",
        "lot_type",
        "lot_id",
        "profile",
        "initial_quantity",
        "accumulated_loss",
        "last_applied_on",
        "is_frozen",
    )
    list_filter = ("organization", "lot_type", "is_frozen")
    search_fields = ("lot_id",)
    readonly_fields = (
        "lot_type",
        "lot_id",
        "initial_quantity",
        "accumulated_loss",
        "last_applied_on",
        "is_frozen",
    )
    autocomplete_fields = ("organization", "profile")


@admin.register(FeedConsumptionPlan)
class FeedConsumptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        "week_start",
        "organization",
        "consumer_module",
        "consumer_batch",
        "consumer_block",
        "recipe",
        "planned_quantity_kg",
        "status",
    )
    list_filter = ("organization", "consumer_module", "status")
    date_hierarchy = "week_start"
    search_fields = ("recipe__code",)
    autocomplete_fields = (
        "organization",
        "consumer_module",
        "consumer_batch",
        "consumer_block",
        "recipe",
    )
