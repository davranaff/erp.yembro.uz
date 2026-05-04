from rest_framework.routers import DefaultRouter

from .views import (
    CurrencyViewSet,
    ExchangeRateViewSet,
    IntegrationSyncLogViewSet,
)


router = DefaultRouter()
router.register(r"currencies", CurrencyViewSet, basename="currency")
router.register(r"rates", ExchangeRateViewSet, basename="exchangerate")
router.register(r"sync-log", IntegrationSyncLogViewSet, basename="sync-log")

app_name = "currency"

urlpatterns = router.urls
