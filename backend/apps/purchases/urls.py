from rest_framework.routers import DefaultRouter

from .views import PurchaseOrderViewSet


router = DefaultRouter()
router.register(r"orders", PurchaseOrderViewSet, basename="purchase-order")

app_name = "purchases"

urlpatterns = router.urls
