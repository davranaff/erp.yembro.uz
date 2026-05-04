from rest_framework.routers import DefaultRouter

from .views import InterModuleTransferViewSet


router = DefaultRouter()
router.register(r"", InterModuleTransferViewSet, basename="transfer")

app_name = "transfers"

urlpatterns = router.urls
