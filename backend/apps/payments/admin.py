from django.contrib import admin

from .models import Payment, PaymentAllocation


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = (
        "target_content_type",
        "target_object_id",
        "amount_uzs",
        "notes",
    )


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "date",
        "direction",
        "channel",
        "status",
        "counterparty",
        "currency",
        "amount_foreign",
        "amount_uzs",
        "organization",
    )
    list_filter = (
        "organization",
        "direction",
        "channel",
        "status",
        "currency",
    )
    date_hierarchy = "date"
    search_fields = ("doc_number", "notes", "counterparty__name", "counterparty__code")
    autocomplete_fields = (
        "organization",
        "module",
        "counterparty",
        "currency",
        "exchange_rate_source",
        "cash_subaccount",
        "journal_entry",
        "created_by",
    )
    inlines = [PaymentAllocationInline]
    readonly_fields = ("journal_entry", "posted_at")


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = (
        "payment",
        "target_content_type",
        "target_object_id",
        "amount_uzs",
    )
    list_filter = ("target_content_type",)
    search_fields = ("payment__doc_number", "notes")
    autocomplete_fields = ("payment",)
