from rest_framework.routers import DefaultRouter

from .views import SaleOrderViewSet


router = DefaultRouter()
router.register(r"orders", SaleOrderViewSet, basename="saleorder")

app_name = "sales"

urlpatterns = router.urls
