from django.contrib import admin

from .models import Counterparty


@admin.register(Counterparty)
class CounterpartyAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "organization",
        "kind",
        "inn",
        "balance_uzs",
        "is_active",
    )
    list_filter = ("organization", "kind", "is_active")
    search_fields = ("code", "name", "inn", "phone", "email")
    autocomplete_fields = ("organization",)
