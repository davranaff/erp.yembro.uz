from django.contrib import admin

from .models import PurchaseItem, PurchaseOrder


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 0
    autocomplete_fields = ("nomenclature",)
    fields = (
        "nomenclature",
        "quantity",
        "unit_price",
        "line_total_foreign",
        "line_total_uzs",
    )


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "date",
        "organization",
        "module",
        "counterparty",
        "warehouse",
        "status",
        "payment_status",
        "currency",
        "exchange_rate",
        "amount_foreign",
        "amount_uzs",
        "paid_amount_uzs",
        "batch",
    )
    list_filter = (
        "organization",
        "module",
        "status",
        "payment_status",
        "currency",
        "date",
    )
    date_hierarchy = "date"
    search_fields = ("doc_number", "counterparty__name", "counterparty__code", "batch__doc_number")
    autocomplete_fields = (
        "organization",
        "module",
        "counterparty",
        "warehouse",
        "currency",
        "exchange_rate_source",
        "batch",
    )
    inlines = [PurchaseItemInline]
