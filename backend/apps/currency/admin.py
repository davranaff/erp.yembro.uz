from django.contrib import admin

from .models import Currency, ExchangeRate, IntegrationSyncLog


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name_ru", "numeric_code", "is_active")
    search_fields = ("code", "name_ru", "name_en")
    list_filter = ("is_active",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "date", "rate", "nominal", "source", "fetched_at")
    list_filter = ("currency", "source")
    date_hierarchy = "date"
    search_fields = ("currency__code",)


@admin.register(IntegrationSyncLog)
class IntegrationSyncLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "status", "occurred_at", "triggered_by")
    list_filter = ("provider", "status")
    date_hierarchy = "occurred_at"
    readonly_fields = (
        "provider",
        "status",
        "occurred_at",
        "triggered_by",
        "stats",
        "error_message",
    )
