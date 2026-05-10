from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BrandViewSet,
    CatalogPageView,
    CategoryViewSet,
    ContactRequestView,
    ProductViewSet,
    SitemapDataView,
)

app_name = "catalog"

router = DefaultRouter()
router.register("brands", BrandViewSet, basename="brand")
router.register("categories", CategoryViewSet, basename="category")
router.register("products", ProductViewSet, basename="product")

urlpatterns = [
    path("v1/", include(router.urls)),
    path("v1/pages/<slug:code>/", CatalogPageView.as_view(), name="page"),
    path("v1/contact/", ContactRequestView.as_view(), name="contact"),
    path("v1/sitemap/", SitemapDataView.as_view(), name="sitemap"),
]
