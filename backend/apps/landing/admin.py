from django.contrib import admin

from .models import DemoLead


@admin.register(DemoLead)
class DemoLeadAdmin(admin.ModelAdmin):
    list_display = ("name", "contact", "company", "notified", "created_at")
    list_filter = ("notified",)
    search_fields = ("name", "contact", "company")
    readonly_fields = ("created_at", "updated_at", "notified")
    ordering = ("-created_at",)
