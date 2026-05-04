from django.contrib import admin

from .models import InterModuleTransfer


@admin.register(InterModuleTransfer)
class InterModuleTransferAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "transfer_date",
        "organization",
        "from_module",
        "to_module",
        "batch",
        "feed_batch",
        "nomenclature",
        "quantity",
        "cost_uzs",
        "state",
    )
    list_filter = ("state", "from_module", "to_module", "organization")
    date_hierarchy = "transfer_date"
    search_fields = (
        "doc_number",
        "notes",
        "batch__doc_number",
        "feed_batch__doc_number",
    )
    autocomplete_fields = (
        "organization",
        "from_module",
        "to_module",
        "from_block",
        "to_block",
        "from_warehouse",
        "to_warehouse",
        "nomenclature",
        "unit",
        "batch",
        "feed_batch",
        "journal_sender",
        "journal_receiver",
        "stock_outgoing",
        "stock_incoming",
    )
    readonly_fields = (
        "journal_sender",
        "journal_receiver",
        "stock_outgoing",
        "stock_incoming",
        "posted_at",
        "reviewed_by",
        "accepted_by",
    )

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.state == InterModuleTransfer.State.POSTED:
            ro.extend(
                f.name
                for f in obj._meta.fields
                if f.name not in ro and f.name != "id"
            )
        return tuple(dict.fromkeys(ro))
