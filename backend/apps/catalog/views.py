"""
Public views каталога.

Все эндпоинты — `permission_classes=[AllowAny]`, без `OrganizationMiddleware`
(он уже выставляет request.organization=None). Lookup для ViewSet'ов идёт по
коду (`code`), потому что переводимые `slug` не уникальны на уровне БД
(через django-modeltranslation `unique=True` ставится только на `slug_ru` и
аналогичных колонках). Фронт получает `slug` нужного языка из ответа и
сам строит URL.
"""
from __future__ import annotations

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from .filters import ProductFilter
from .i18n import LANGS, localized, resolve_lang
from .models import Brand, CatalogPage, Category, Product, ProductImage
from .serializers import (
    BrandListSerializer,
    CatalogPageSerializer,
    CategoryNodeSerializer,
    ContactRequestSerializer,
    ProductCardSerializer,
    ProductDetailSerializer,
)
from .tasks import notify_contact_request_task

CACHE_SECONDS = 60 * 15
LIST_CACHE_DECORATORS = (
    vary_on_headers("Accept-Language"),
    cache_page(CACHE_SECONDS),
)


def _cache_view(view):
    for d in LIST_CACHE_DECORATORS:
        view = d(view)
    return view


class _PublicMixin:
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["lang"] = resolve_lang(self.request)
        return ctx


class BrandViewSet(_PublicMixin, viewsets.ReadOnlyModelViewSet):
    """
    GET /brands/        → список активных брендов
    GET /brands/<code>/ → бренд + featured products
    """
    serializer_class = BrandListSerializer
    lookup_field = "code"
    lookup_value_regex = r"[\w-]+"

    def get_queryset(self):
        return Brand.objects.filter(is_active=True).order_by("sort_order", "id")

    @method_decorator(LIST_CACHE_DECORATORS[0])
    @method_decorator(LIST_CACHE_DECORATORS[1])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def retrieve(self, request, *args, **kwargs):
        brand = self.get_object()
        ctx = self.get_serializer_context()
        data = BrandListSerializer(brand, context=ctx).data
        featured_qs = (
            Product.objects.filter(brand=brand, is_active=True, is_featured=True)
            .select_related("brand", "category")
            .prefetch_related("images")
            .order_by("sort_order", "id")[:12]
        )
        data["featured"] = ProductCardSerializer(featured_qs, many=True, context=ctx).data
        return Response(data)


class CategoryViewSet(_PublicMixin, viewsets.ReadOnlyModelViewSet):
    """
    GET /categories/        → плоское дерево (level/lft/rght/tree_id)
    GET /categories/<code>/ → категория + breadcrumbs + потомки
    """
    serializer_class = CategoryNodeSerializer
    lookup_field = "code"
    lookup_value_regex = r"[\w-]+"

    def get_queryset(self):
        return Category.objects.filter(is_active=True)

    @method_decorator(LIST_CACHE_DECORATORS[0])
    @method_decorator(LIST_CACHE_DECORATORS[1])
    def list(self, request, *args, **kwargs):
        # Дерево: упорядочено по mptt-обходу.
        qs = self.get_queryset().order_by("tree_id", "lft")
        ctx = self.get_serializer_context()
        return Response(CategoryNodeSerializer(qs, many=True, context=ctx).data)

    def retrieve(self, request, *args, **kwargs):
        cat = self.get_object()
        ctx = self.get_serializer_context()
        lang = ctx["lang"]
        breadcrumbs = [
            {
                "code": c.code,
                "slug": localized(c, "slug", lang) or c.code,
                "name": localized(c, "name", lang),
            }
            for c in cat.get_ancestors(include_self=True)
        ]
        children_qs = cat.get_children().filter(is_active=True)
        return Response({
            **CategoryNodeSerializer(cat, context=ctx).data,
            "breadcrumbs": breadcrumbs,
            "children": CategoryNodeSerializer(children_qs, many=True, context=ctx).data,
        })


class ProductViewSet(_PublicMixin, viewsets.ReadOnlyModelViewSet):
    """
    GET /products/        → пагинированный список с фильтрами
    GET /products/<code>/ → карточка с spec + images + breadcrumbs + related
    """
    filterset_class = ProductFilter
    lookup_field = "code"
    lookup_value_regex = r"[\w-]+"
    search_fields = ("name_ru", "name_uz", "name_en", "description_ru", "description_uz", "description_en")
    ordering_fields = ("sort_order", "created_at", "updated_at")
    ordering = ("sort_order", "id")

    def get_queryset(self):
        return (
            Product.objects.filter(is_active=True)
            .select_related("brand", "category", "spec")
            .prefetch_related(
                Prefetch(
                    "images",
                    queryset=ProductImage.objects.order_by("-is_primary", "sort_order"),
                ),
            )
        )

    def get_serializer_class(self):
        return ProductCardSerializer if self.action == "list" else ProductDetailSerializer

    @method_decorator(LIST_CACHE_DECORATORS[0])
    @method_decorator(LIST_CACHE_DECORATORS[1])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class CatalogPageView(_PublicMixin, APIView):
    """GET /pages/<code>/ → статичная страница (about, contacts, erp...)."""

    def get(self, request, code: str):
        page = get_object_or_404(
            CatalogPage.objects.filter(is_published=True), code=code,
        )
        return Response(CatalogPageSerializer(page, context={
            "lang": resolve_lang(request), "request": request,
        }).data)


# ── Contact form ────────────────────────────────────────────────────────────

class ContactAnonThrottle(AnonRateThrottle):
    scope = "catalog-contact"


class ContactRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ContactAnonThrottle]

    def post(self, request):
        s = ContactRequestSerializer(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)

        # Honeypot: тихо принимаем без сохранения.
        if s.context.get("_honeypot_triggered"):
            return Response({"ok": True}, status=status.HTTP_201_CREATED)

        ip = (request.META.get("HTTP_X_FORWARDED_FOR", "") or request.META.get("REMOTE_ADDR", "")).split(",")[0].strip() or None
        ua = request.META.get("HTTP_USER_AGENT", "")[:400]
        instance = s.save(ip=ip, user_agent=ua)
        notify_contact_request_task.delay(str(instance.id))
        return Response({"ok": True}, status=status.HTTP_201_CREATED)


# ── Sitemap data ────────────────────────────────────────────────────────────

class SitemapDataView(APIView):
    """
    GET /sitemap/ → плоский JSON всех публичных URL для генерации sitemap.xml
    в Next.js. Возвращает alternates для 3 языков.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(cache_page(CACHE_SECONDS))
    def get(self, request):
        items: list[dict] = []

        def emit(kind: str, code: str, slugs_by_lang: dict, updated, priority: float, changefreq: str):
            entry = {
                "kind": kind,
                "code": code,
                "lastmod": updated.isoformat() if updated else None,
                "changefreq": changefreq,
                "priority": priority,
                "alternates": {},
            }
            for lng in LANGS:
                slug = slugs_by_lang.get(lng) or slugs_by_lang.get("ru") or code
                entry["alternates"][lng] = slug
            items.append(entry)

        for b in Brand.objects.filter(is_active=True):
            emit("brand", b.code, {l: getattr(b, f"slug_{l}", None) for l in LANGS}, b.updated_at, 0.6, "weekly")
        for c in Category.objects.filter(is_active=True):
            emit("category", c.code, {l: getattr(c, f"slug_{l}", None) for l in LANGS}, c.updated_at, 0.7, "weekly")
        for p in Product.objects.filter(is_active=True).only("code", "updated_at", *[f"slug_{l}" for l in LANGS]):
            emit("product", p.code, {l: getattr(p, f"slug_{l}", None) for l in LANGS}, p.updated_at, 0.8, "weekly")
        for pg in CatalogPage.objects.filter(is_published=True):
            emit("page", pg.code, {l: getattr(pg, f"slug_{l}", None) for l in LANGS}, pg.updated_at, 0.5, "monthly")

        return Response({"items": items, "languages": list(LANGS)})
