from rest_framework.routers import DefaultRouter

from .views import ProductionBlockViewSet, StockMovementViewSet, WarehouseViewSet


router = DefaultRouter()
router.register(r"blocks", ProductionBlockViewSet, basename="productionblock")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"movements", StockMovementViewSet, basename="stockmovement")

app_name = "warehouses"

urlpatterns = router.urls
