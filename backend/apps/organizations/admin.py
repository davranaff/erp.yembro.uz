from django.contrib import admin

from .models import Organization, OrganizationMembership


class OrganizationMembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    autocomplete_fields = ("user",)
    fields = (
        "user",
        "position_title",
        "work_phone",
        "work_status",
        "is_active",
    )


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "direction", "accounting_currency", "is_active")
    list_filter = ("direction", "is_active")
    search_fields = ("code", "name", "legal_name", "inn")
    autocomplete_fields = ("accounting_currency",)
    inlines = [OrganizationMembershipInline]


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "organization",
        "position_title",
        "work_phone",
        "work_status",
        "is_active",
        "joined_at",
    )
    list_filter = ("organization", "work_status", "is_active")
    search_fields = (
        "user__email",
        "user__full_name",
        "position_title",
        "work_phone",
        "organization__code",
    )
    autocomplete_fields = ("user", "organization")
