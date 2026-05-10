"""
Регистрация переводимых полей django-modeltranslation.

После регистрации в БД появляются колонки `name_ru/name_uz/name_en` и т.д.,
а оригинальные `name`/`description` становятся виртуальными полями, которые
проксируют запись в активный язык (django.utils.translation).
"""
from modeltranslation.translator import TranslationOptions, register

from .models import Brand, CatalogPage, Category, Product, ProductImage


@register(Brand)
class BrandTranslationOptions(TranslationOptions):
    fields = ("slug", "name", "description", "meta_title", "meta_description")


@register(Category)
class CategoryTranslationOptions(TranslationOptions):
    fields = ("slug", "name", "description", "meta_title", "meta_description")


@register(Product)
class ProductTranslationOptions(TranslationOptions):
    fields = (
        "slug",
        "name",
        "short_description",
        "description",
        "application",
        "meta_title",
        "meta_description",
    )


@register(ProductImage)
class ProductImageTranslationOptions(TranslationOptions):
    fields = ("alt",)


@register(CatalogPage)
class CatalogPageTranslationOptions(TranslationOptions):
    fields = ("slug", "title", "body", "meta_title", "meta_description")
