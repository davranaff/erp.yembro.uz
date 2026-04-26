from django.contrib import admin

from .models import Module, OrganizationModule


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "kind", "sort_order", "is_active")
    list_filter = ("kind", "is_active")
    search_fields = ("code", "name")


@admin.register(OrganizationModule)
class OrganizationModuleAdmin(admin.ModelAdmin):
    list_display = ("organization", "module", "is_enabled", "enabled_at")
    list_filter = ("is_enabled", "module")
    search_fields = ("organization__code", "module__code")
    autocomplete_fields = ("organization", "module")
