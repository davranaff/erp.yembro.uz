from django.contrib import admin

from .models import Batch, BatchChainStep, BatchCostEntry


class BatchCostEntryInline(admin.TabularInline):
    model = BatchCostEntry
    extra = 0
    autocomplete_fields = ("module",)
    fields = ("category", "amount_uzs", "module", "occurred_at", "description")


class BatchChainStepInline(admin.TabularInline):
    model = BatchChainStep
    extra = 0
    max_num = 0
    can_delete = False
    readonly_fields = (
        "sequence",
        "module",
        "block",
        "entered_at",
        "exited_at",
        "quantity_in",
        "quantity_out",
        "accumulated_cost_at_exit",
        "transfer_in",
        "transfer_out",
        "note",
    )
    fields = readonly_fields


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "organization",
        "nomenclature",
        "state",
        "current_module",
        "current_block",
        "current_quantity",
        "accumulated_cost_uzs",
        "started_at",
        "withdrawal_period_ends",
    )
    list_filter = (
        "state",
        "current_module",
        "origin_module",
        "organization",
        "withdrawal_period_ends",
    )
    search_fields = ("doc_number", "notes", "nomenclature__sku", "nomenclature__name")
    date_hierarchy = "started_at"
    autocomplete_fields = (
        "organization",
        "nomenclature",
        "unit",
        "origin_module",
        "current_module",
        "current_block",
        "parent_batch",
        "origin_purchase",
        "origin_counterparty",
    )
    readonly_fields = ("accumulated_cost_uzs",)
    inlines = [BatchCostEntryInline, BatchChainStepInline]


@admin.register(BatchCostEntry)
class BatchCostEntryAdmin(admin.ModelAdmin):
    list_display = ("batch", "category", "amount_uzs", "module", "occurred_at")
    list_filter = ("category", "module", "occurred_at")
    date_hierarchy = "occurred_at"
    search_fields = ("batch__doc_number", "description")
    autocomplete_fields = ("batch", "module")


@admin.register(BatchChainStep)
class BatchChainStepAdmin(admin.ModelAdmin):
    list_display = (
        "batch",
        "sequence",
        "module",
        "block",
        "entered_at",
        "exited_at",
        "quantity_in",
        "quantity_out",
    )
    list_filter = ("module",)
    search_fields = ("batch__doc_number",)
    autocomplete_fields = ("batch", "module", "block", "transfer_in", "transfer_out")
