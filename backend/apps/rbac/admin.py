from django.contrib import admin

from .models import Role, RolePermission, UserModuleAccessOverride, UserRole


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0
    autocomplete_fields = ("module",)
    fields = ("module", "level")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("organization", "code", "name", "is_system", "is_active")
    list_filter = ("organization", "is_system", "is_active")
    search_fields = ("code", "name")
    autocomplete_fields = ("organization",)
    inlines = [RolePermissionInline]


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("membership", "role", "assigned_at", "assigned_by")
    list_filter = ("role__organization",)
    search_fields = (
        "membership__user__email",
        "membership__user__full_name",
        "role__name",
    )
    autocomplete_fields = ("membership", "role", "assigned_by")


@admin.register(UserModuleAccessOverride)
class UserModuleAccessOverrideAdmin(admin.ModelAdmin):
    list_display = ("membership", "module", "level", "reason")
    list_filter = ("module", "level")
    search_fields = (
        "membership__user__email",
        "membership__user__full_name",
        "module__code",
    )
    autocomplete_fields = ("membership", "module")
