from django.contrib import admin

from .models import GLAccount, GLSubaccount, JournalEntry


@admin.register(GLAccount)
class GLAccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "type")
    list_filter = ("organization", "type")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization",)


@admin.register(GLSubaccount)
class GLSubaccountAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "account", "module")
    list_filter = ("account", "module")
    search_fields = ("code", "name")
    autocomplete_fields = ("account", "module")


@admin.register(JournalEntry)
class JournalEntryAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number",
        "entry_date",
        "organization",
        "module",
        "debit_subaccount",
        "credit_subaccount",
        "amount_uzs",
        "currency",
        "batch",
    )
    list_filter = ("organization", "module", "entry_date", "currency")
    search_fields = ("doc_number", "description", "batch__doc_number")
    date_hierarchy = "entry_date"
    autocomplete_fields = (
        "organization",
        "module",
        "debit_subaccount",
        "credit_subaccount",
        "counterparty",
        "currency",
        "batch",
    )
