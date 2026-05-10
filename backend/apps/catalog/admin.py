"""
Django admin с табами языков (django-modeltranslation) и MPTT-tree.
"""
from __future__ import annotations

from django.contrib import admin
from modeltranslation.admin import TabbedTranslationAdmin, TranslationStackedInline
from mptt.admin import DraggableMPTTAdmin, TreeRelatedFieldListFilter

from .models import (
    Brand,
    CatalogPage,
    Category,
    ContactRequest,
    Product,
    ProductImage,
    ProductSpec,
)


class _MPTTTabbedAdmin(DraggableMPTTAdmin, TabbedTranslationAdmin):
    """DraggableMPTT + табы языков. MRO: DraggableMPTT первым, чтобы переопределить changelist."""


@admin.register(Brand)
class BrandAdmin(TabbedTranslationAdmin):
    list_display = ("code", "name", "is_active", "sort_order")
    list_filter = ("is_active",)
    search_fields = ("code", "name", "name_ru", "name_uz", "name_en")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug_ru": ("name_ru",)}
    fieldsets = (
        (None, {"fields": ("code", "is_active", "sort_order", "logo")}),
        ("Контент", {"fields": ("name", "slug", "description")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "og_image")}),
    )


@admin.register(Category)
class CategoryAdmin(_MPTTTabbedAdmin):
    list_display = ("tree_actions", "indented_title", "code", "direction", "is_active", "sort_order")
    list_display_links = ("indented_title",)
    list_filter = ("is_active", "direction", ("parent", TreeRelatedFieldListFilter))
    search_fields = ("code", "name", "name_ru", "name_uz", "name_en")
    list_editable = ("is_active", "sort_order")
    prepopulated_fields = {"slug_ru": ("name_ru",)}
    fieldsets = (
        (None, {"fields": ("code", "parent", "direction", "is_active", "sort_order", "image")}),
        ("Контент", {"fields": ("name", "slug", "description")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "og_image")}),
    )


class ProductImageInline(TranslationStackedInline):
    model = ProductImage
    extra = 0
    fields = ("image", "alt", "sort_order", "is_primary")


class ProductSpecInline(admin.StackedInline):
    model = ProductSpec
    extra = 0
    can_delete = False


@admin.register(Product)
class ProductAdmin(TabbedTranslationAdmin):
    list_display = (
        "code", "name", "brand", "category", "direction",
        "is_featured", "is_active", "sort_order",
    )
    list_filter = ("is_active", "is_featured", "direction", "brand", ("category", TreeRelatedFieldListFilter))
    search_fields = ("code", "name", "name_ru", "name_uz", "name_en", "description_ru")
    list_editable = ("is_featured", "is_active", "sort_order")
    list_select_related = ("brand", "category")
    autocomplete_fields = ("brand", "category")
    prepopulated_fields = {"slug_ru": ("name_ru",)}
    inlines = (ProductSpecInline, ProductImageInline)
    fieldsets = (
        (None, {"fields": ("code", "brand", "category", "direction",
                            "is_active", "is_featured", "sort_order")}),
        ("Возраст / фасовка", {"fields": ("age_from_days", "age_to_days", "package_kg")}),
        ("Контент", {"fields": ("name", "slug", "short_description", "description", "application")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "og_image")}),
    )


@admin.register(CatalogPage)
class CatalogPageAdmin(TabbedTranslationAdmin):
    list_display = ("code", "title", "is_published", "updated_at")
    list_filter = ("is_published",)
    search_fields = ("code", "title", "title_ru", "title_uz", "title_en")
    list_editable = ("is_published",)
    prepopulated_fields = {"slug_ru": ("title_ru",)}
    fieldsets = (
        (None, {"fields": ("code", "is_published")}),
        ("Контент", {"fields": ("title", "slug", "body")}),
        ("SEO", {"fields": ("meta_title", "meta_description", "og_image")}),
    )


@admin.register(ContactRequest)
class ContactRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "contact", "company", "source_lang", "notified", "created_at")
    list_filter = ("notified", "source_lang")
    search_fields = ("name", "contact", "company", "message")
    readonly_fields = (
        "name", "contact", "company", "message",
        "source_lang", "source_url", "user_agent", "ip",
        "notified", "created_at", "updated_at",
    )
    ordering = ("-created_at",)
