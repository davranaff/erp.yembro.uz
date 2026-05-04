from rest_framework.routers import DefaultRouter

from .views import PurchaseAttachmentViewSet, PurchaseOrderViewSet


router = DefaultRouter()
router.register(r"orders", PurchaseOrderViewSet, basename="purchase-order")
router.register(
    r"attachments", PurchaseAttachmentViewSet, basename="purchase-attachment"
)

app_name = "purchases"

urlpatterns = router.urls
