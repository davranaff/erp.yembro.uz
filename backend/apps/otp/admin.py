from django.contrib import admin

from .models import OtpCode, SmsMessage


@admin.register(OtpCode)
class OtpCodeAdmin(admin.ModelAdmin):
    list_display = (
        "phone",
        "purpose",
        "attempts",
        "max_attempts",
        "expires_at",
        "used_at",
        "created_at",
    )
    list_filter = ("purpose",)
    search_fields = ("phone",)
    readonly_fields = (
        "phone",
        "purpose",
        "code_hash",
        "attempts",
        "max_attempts",
        "expires_at",
        "used_at",
        "requested_ip",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False


@admin.register(SmsMessage)
class SmsMessageAdmin(admin.ModelAdmin):
    list_display = (
        "phone",
        "source",
        "status",
        "sent_at",
        "delivered_at",
        "cost_uzs",
        "created_at",
    )
    list_filter = ("source", "status")
    search_fields = ("phone", "provider_message_id", "message")
    readonly_fields = (
        "phone",
        "message",
        "source",
        "purpose",
        "status",
        "provider_message_id",
        "provider_response",
        "sent_at",
        "delivered_at",
        "failed_at",
        "error_msg",
        "cost_uzs",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
