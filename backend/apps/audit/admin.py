from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "occurred_at",
        "organization",
        "module",
        "actor",
        "action",
        "entity_repr",
    )
    list_filter = ("organization", "module", "action")
    date_hierarchy = "occurred_at"
    search_fields = ("entity_repr", "action_verb", "actor__email")
    readonly_fields = tuple(
        f.name for f in AuditLog._meta.get_fields() if hasattr(f, "name")
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
