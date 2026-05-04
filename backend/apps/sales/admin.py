from django.contrib import admin

from .models import SaleItem, SaleOrder


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("cost_per_unit_uzs", "line_total_uzs", "line_cost_uzs", "created_at", "updated_at")
    autocomplete_fields = ("nomenclature",)


@admin.register(SaleOrder)
class SaleOrderAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number", "date", "module", "customer",
        "status", "payment_status", "amount_uzs", "cost_uzs",
    )
    list_filter = ("status", "payment_status", "module", "currency")
    search_fields = ("doc_number", "customer__name", "customer__code", "notes")
    autocomplete_fields = ("customer", "warehouse", "currency", "module")
    readonly_fields = (
        "amount_foreign", "amount_uzs", "cost_uzs",
        "exchange_rate", "exchange_rate_source",
        "paid_amount_uzs", "payment_status",
        "created_at", "updated_at",
    )
    inlines = [SaleItemInline]
    date_hierarchy = "date"
