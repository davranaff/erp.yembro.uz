from django.contrib import admin

from .models import OtpCode


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
