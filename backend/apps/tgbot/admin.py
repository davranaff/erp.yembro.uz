from django.contrib import admin

from .models import TgLink, TgLinkToken


@admin.register(TgLink)
class TgLinkAdmin(admin.ModelAdmin):
    list_display = ("chat_id", "tg_username", "user", "counterparty", "organization", "is_active", "created_at")
    list_filter = ("is_active", "organization")
    search_fields = ("chat_id", "tg_username", "user__email", "counterparty__name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(TgLinkToken)
class TgLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("token", "user", "counterparty", "organization", "expires_at", "used")
    list_filter = ("used", "organization")
    readonly_fields = ("token", "expires_at", "created_at")
