"""
Public-сериализаторы каталога.

Все поля, которые имеют переводимые версии (`_ru/_uz/_en`), сериализуются
в плоский ключ с применением `localized()`. Это держит JSON компактным
для фронта и не утечёт в API лишние языки кроме запрошенного.
"""
from __future__ import annotations

import re

from rest_framework import serializers

from .i18n import DEFAULT_LANG, localized
from .models import (
    Brand,
    CatalogPage,
    Category,
    ContactRequest,
    Product,
    ProductImage,
    ProductSpec,
)


class _LocalizedMixin:
    """Делает контекстный язык доступным как self.lang."""

    @property
    def lang(self) -> str:
        return self.context.get("lang") or DEFAULT_LANG


class BrandListSerializer(_LocalizedMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = (
            "id", "code", "slug", "name", "description",
            "logo", "meta_title", "meta_description", "og_image", "sort_order",
        )

    def get_name(self, obj): return localized(obj, "name", self.lang)
    def get_slug(self, obj): return localized(obj, "slug", self.lang) or obj.code
    def get_description(self, obj): return localized(obj, "description", self.lang)
    def get_meta_title(self, obj): return localized(obj, "meta_title", self.lang)
    def get_meta_description(self, obj): return localized(obj, "meta_description", self.lang)


class CategoryNodeSerializer(_LocalizedMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()
    parent_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = Category
        fields = (
            "id", "code", "slug", "name", "description", "image",
            "direction", "meta_title", "meta_description", "og_image",
            "parent_id", "level", "lft", "rght", "tree_id", "sort_order",
        )

    def get_name(self, obj): return localized(obj, "name", self.lang)
    def get_slug(self, obj): return localized(obj, "slug", self.lang) or obj.code
    def get_description(self, obj): return localized(obj, "description", self.lang)
    def get_meta_title(self, obj): return localized(obj, "meta_title", self.lang)
    def get_meta_description(self, obj): return localized(obj, "meta_description", self.lang)


def _absolute_media_url(image_field) -> str | None:
    """Безопасное построение абсолютного URL для медиа-файла.

    Не зависит от request.Host (который в docker-internal среде может быть
    'prod-api:30000'). Использует CATALOG_PUBLIC_MEDIA_BASE из settings —
    обычно это 'https://api.erp.yembro.uz'.
    """
    from django.conf import settings
    if not image_field:
        return None
    try:
        url = image_field.url  # /media/catalog/products/...
    except Exception:
        return None
    base = getattr(settings, "CATALOG_PUBLIC_MEDIA_BASE", "") or ""
    if base:
        return base.rstrip("/") + url
    return url


class ProductImageSerializer(_LocalizedMixin, serializers.ModelSerializer):
    alt = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt", "sort_order", "is_primary")

    def get_alt(self, obj): return localized(obj, "alt", self.lang)

    def get_image(self, obj):
        return _absolute_media_url(obj.image)


class ProductSpecSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductSpec
        exclude = ("id", "product")


class ProductCardSerializer(_LocalizedMixin, serializers.ModelSerializer):
    """Краткая карточка для списков (главная, категории, поиск)."""
    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    short_description = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    primary_image = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "code", "slug", "name", "short_description",
            "brand", "category", "direction", "package_kg",
            "age_from_days", "age_to_days", "is_featured", "primary_image",
        )

    def get_name(self, obj): return localized(obj, "name", self.lang)
    def get_slug(self, obj): return localized(obj, "slug", self.lang) or obj.code
    def get_short_description(self, obj): return localized(obj, "short_description", self.lang)

    def get_brand(self, obj):
        return {
            "id": str(obj.brand_id),
            "code": obj.brand.code,
            "slug": localized(obj.brand, "slug", self.lang) or obj.brand.code,
            "name": localized(obj.brand, "name", self.lang),
        }

    def get_category(self, obj):
        return {
            "id": str(obj.category_id),
            "code": obj.category.code,
            "slug": localized(obj.category, "slug", self.lang) or obj.category.code,
            "name": localized(obj.category, "name", self.lang),
        }

    def get_primary_image(self, obj):
        img = next(
            (i for i in obj.images.all() if i.is_primary),
            next(iter(obj.images.all()), None),
        )
        return _absolute_media_url(img.image) if img else None


class ProductDetailSerializer(_LocalizedMixin, serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    short_description = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    application = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()
    brand = serializers.SerializerMethodField()
    category = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()
    images = serializers.SerializerMethodField()
    spec = ProductSpecSerializer(read_only=True)
    related = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id", "code", "slug", "name", "short_description", "description",
            "application", "brand", "category", "direction", "package_kg",
            "age_from_days", "age_to_days", "meta_title", "meta_description",
            "og_image", "images", "spec", "breadcrumbs", "related", "updated_at",
        )

    def get_name(self, obj): return localized(obj, "name", self.lang)
    def get_slug(self, obj): return localized(obj, "slug", self.lang) or obj.code
    def get_short_description(self, obj): return localized(obj, "short_description", self.lang)
    def get_description(self, obj): return localized(obj, "description", self.lang)
    def get_application(self, obj): return localized(obj, "application", self.lang)
    def get_meta_title(self, obj): return localized(obj, "meta_title", self.lang)
    def get_meta_description(self, obj): return localized(obj, "meta_description", self.lang)

    def get_brand(self, obj):
        return BrandListSerializer(obj.brand, context=self.context).data

    def get_category(self, obj):
        return CategoryNodeSerializer(obj.category, context=self.context).data

    def get_breadcrumbs(self, obj):
        chain = list(obj.category.get_ancestors(include_self=True))
        return [
            {
                "code": c.code,
                "slug": localized(c, "slug", self.lang) or c.code,
                "name": localized(c, "name", self.lang),
            }
            for c in chain
        ]

    def get_images(self, obj):
        return ProductImageSerializer(
            obj.images.all().order_by("-is_primary", "sort_order"),
            many=True,
            context=self.context,
        ).data

    def get_related(self, obj):
        qs = (
            Product.objects.filter(category_id=obj.category_id, is_active=True)
            .exclude(id=obj.id)
            .select_related("brand", "category")
            .prefetch_related("images")[:6]
        )
        return ProductCardSerializer(qs, many=True, context=self.context).data


class CatalogPageSerializer(_LocalizedMixin, serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    meta_title = serializers.SerializerMethodField()
    meta_description = serializers.SerializerMethodField()

    class Meta:
        model = CatalogPage
        fields = (
            "id", "code", "slug", "title", "body",
            "meta_title", "meta_description", "og_image", "updated_at",
        )

    def get_title(self, obj): return localized(obj, "title", self.lang)
    def get_slug(self, obj): return localized(obj, "slug", self.lang) or obj.code
    def get_body(self, obj): return localized(obj, "body", self.lang)
    def get_meta_title(self, obj): return localized(obj, "meta_title", self.lang)
    def get_meta_description(self, obj): return localized(obj, "meta_description", self.lang)


# ── Contact form ────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"^\+?[\d\s\-()]{7,}$")
_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class ContactRequestSerializer(serializers.ModelSerializer):
    # Honeypot — невидимое поле, заполняется только ботами.
    website = serializers.CharField(
        required=False, allow_blank=True, write_only=True,
    )

    class Meta:
        model = ContactRequest
        fields = (
            "name", "contact", "company", "message",
            "source_lang", "source_url", "website",
        )
        extra_kwargs = {
            "name": {"min_length": 2, "max_length": 100},
            "contact": {"min_length": 5, "max_length": 100},
            "company": {"required": False, "allow_blank": True, "max_length": 100},
            "message": {"required": False, "allow_blank": True, "max_length": 2000},
            "source_lang": {"required": False, "default": "ru"},
            "source_url": {"required": False, "allow_blank": True},
        }

    def validate_contact(self, value: str) -> str:
        v = value.strip()
        if not (_PHONE_RE.match(v) or _EMAIL_RE.match(v)):
            raise serializers.ValidationError("Укажите корректный телефон или email.")
        return v

    def validate_name(self, value: str) -> str:
        v = value.strip()
        if not re.search(r"[a-zA-Zа-яА-ЯёЁ]", v):
            raise serializers.ValidationError("Укажите имя.")
        return v

    def validate_source_lang(self, value: str) -> str:
        return value if value in ("ru", "uz", "en") else "ru"

    def validate(self, attrs):
        honey = attrs.pop("website", "")
        if honey and honey.strip():
            self.context["_honeypot_triggered"] = True
        return attrs
