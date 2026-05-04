from rest_framework.routers import DefaultRouter

from .views import SaleCommunicationViewSet, SaleOrderViewSet


router = DefaultRouter()
router.register(r"orders", SaleOrderViewSet, basename="saleorder")
router.register(
    r"communications", SaleCommunicationViewSet, basename="salecommunication"
)

app_name = "sales"

urlpatterns = router.urls
