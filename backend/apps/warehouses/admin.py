from django.contrib import admin

from .models import ProductionBlock, StockMovement, Warehouse


@admin.register(ProductionBlock)
class ProductionBlockAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "module", "kind", "capacity", "is_active")
    list_filter = ("organization", "module", "kind", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization", "module", "capacity_unit")


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "module", "production_block", "is_active")
    list_filter = ("organization", "module", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = (
        "organization",
        "module",
        "production_block",
        "default_gl_subaccount",
    )


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "date",
        "organization",
        "module",
        "kind",
        "nomenclature",
        "quantity",
        "amount_uzs",
        "counterparty",
        "batch",
    )
    list_filter = ("organization", "module", "kind", "date")
    date_hierarchy = "date"
    search_fields = ("doc_number", "batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "nomenclature",
        "warehouse_from",
        "warehouse_to",
        "counterparty",
        "batch",
    )
