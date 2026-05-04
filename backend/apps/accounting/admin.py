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


from .models import CashAdvance


from .models import ExpenseArticle


@admin.register(ExpenseArticle)
class ExpenseArticleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "organization", "default_module", "is_active")
    list_filter = ("organization", "kind", "is_active")
    search_fields = ("code", "name", "notes")
    autocomplete_fields = ("organization", "default_module", "default_subaccount", "parent")


@admin.register(CashAdvance)
class CashAdvanceAdmin(admin.ModelAdmin):
    list_display = (
        "doc_number", "organization", "issued_date", "recipient",
        "amount_uzs", "spent_amount_uzs", "returned_amount_uzs",
        "status", "expense_article",
    )
    list_filter = ("organization", "status", "expense_article")
    search_fields = ("doc_number", "purpose", "recipient__email", "recipient__full_name")
    date_hierarchy = "issued_date"
    autocomplete_fields = (
        "organization", "recipient", "expense_article",
        "issued_payment", "closing_journal_entry", "created_by",
    )
    readonly_fields = (
        "doc_number", "spent_amount_uzs", "returned_amount_uzs",
        "closed_date", "closing_journal_entry",
    )
