from django.contrib import admin

from .models import Category, NomenclatureItem, Unit


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization")
    list_filter = ("organization",)
    search_fields = ("code", "name")
    autocomplete_fields = ("organization",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "parent", "default_gl_subaccount")
    search_fields = ("name",)
    list_filter = ("organization", "parent")
    autocomplete_fields = ("organization", "parent", "default_gl_subaccount")


@admin.register(NomenclatureItem)
class NomenclatureItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "organization", "category", "unit", "is_active")
    list_filter = ("organization", "category", "is_active")
    search_fields = ("sku", "name", "barcode")
    autocomplete_fields = ("organization", "category", "unit", "default_gl_subaccount")
