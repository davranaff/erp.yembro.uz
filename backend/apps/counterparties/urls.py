from rest_framework.routers import DefaultRouter

from .views import CounterpartyViewSet


router = DefaultRouter()
router.register(r"", CounterpartyViewSet, basename="counterparty")

app_name = "counterparties"

urlpatterns = router.urls
