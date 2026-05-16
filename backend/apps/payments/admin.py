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

    # Защита от случайных правок проведённых/отменённых платежей через
    # админку. К ним привязана JournalEntry — изменив сумму/счёт через
    # django-admin, оператор сломал бы баланс ГК без сторно. Меняем
    # только DRAFT; POSTED/CANCELLED делаются readonly целиком.
    def get_readonly_fields(self, request, obj=None):
        base = list(super().get_readonly_fields(request, obj))
        if obj is not None and obj.status in (
            Payment.Status.POSTED, Payment.Status.CANCELLED,
        ):
            return [f.name for f in self.model._meta.fields] + ["journal_entry"]
        return base

    def has_delete_permission(self, request, obj=None):
        # POSTED платёж нельзя удалить — сначала reverse_payment().
        if obj is not None and obj.status == Payment.Status.POSTED:
            return False
        return super().has_delete_permission(request, obj)


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
