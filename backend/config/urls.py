from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)


def healthcheck(_request):
    """Liveness probe used by CI/CD and Docker healthchecks."""
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health", healthcheck, name="healthcheck"),
    path("health/", healthcheck),
    path("admin/", admin.site.urls),
    # Auth
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path(
        "api/auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),
    path(
        "api/auth/token/verify/",
        TokenVerifyView.as_view(),
        name="token_verify",
    ),
    # OpenAPI
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(url_name="schema"),
        name="redoc",
    ),
    # Apps
    path("api/users/", include("apps.users.urls", namespace="users")),
    path(
        "api/counterparties/",
        include("apps.counterparties.urls", namespace="counterparties"),
    ),
    path(
        "api/currency/",
        include("apps.currency.urls", namespace="currency"),
    ),
    path(
        "api/purchases/",
        include("apps.purchases.urls", namespace="purchases"),
    ),
    path(
        "api/payments/",
        include("apps.payments.urls", namespace="payments"),
    ),
    path(
        "api/nomenclature/",
        include("apps.nomenclature.urls", namespace="nomenclature"),
    ),
    path(
        "api/warehouses/",
        include("apps.warehouses.urls", namespace="warehouses"),
    ),
    path(
        "api/transfers/",
        include("apps.transfers.urls", namespace="transfers"),
    ),
    path(
        "api/feed/",
        include("apps.feed.urls", namespace="feed"),
    ),
    path(
        "api/vet/",
        include("apps.vet.urls", namespace="vet"),
    ),
    path("api/", include("apps.modules.urls", namespace="modules")),
    path("api/", include("apps.organizations.urls", namespace="organizations")),
    path("api/", include("apps.batches.urls", namespace="batches")),
    path(
        "api/accounting/",
        include("apps.accounting.urls", namespace="accounting"),
    ),
    path(
        "api/audit/",
        include("apps.audit.urls", namespace="audit"),
    ),
    path(
        "api/rbac/",
        include("apps.rbac.urls", namespace="rbac"),
    ),
    path(
        "api/matochnik/",
        include("apps.matochnik.urls", namespace="matochnik"),
    ),
    path(
        "api/incubation/",
        include("apps.incubation.urls", namespace="incubation"),
    ),
    path(
        "api/feedlot/",
        include("apps.feedlot.urls", namespace="feedlot"),
    ),
    path(
        "api/slaughter/",
        include("apps.slaughter.urls", namespace="slaughter"),
    ),
    path(
        "api/holding/",
        include("apps.holding.urls", namespace="holding"),
    ),
    path(
        "api/dashboard/",
        include("apps.dashboard.urls", namespace="dashboard"),
    ),
    path(
        "api/sales/",
        include("apps.sales.urls", namespace="sales"),
    ),
    path("api/tg/", include("apps.tgbot.urls")),
    path("api/landing/", include("apps.landing.urls", namespace="landing")),
]
