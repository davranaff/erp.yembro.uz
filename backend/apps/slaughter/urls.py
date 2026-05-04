from rest_framework.routers import DefaultRouter

from .views import (
    SlaughterLabTestViewSet,
    SlaughterQualityCheckViewSet,
    SlaughterShiftViewSet,
    SlaughterYieldViewSet,
)


router = DefaultRouter()
router.register(r"shifts", SlaughterShiftViewSet, basename="slaughtershift")
router.register(r"yields", SlaughterYieldViewSet, basename="slaughteryield")
router.register(r"quality-checks", SlaughterQualityCheckViewSet, basename="qualitycheck")
router.register(r"lab-tests", SlaughterLabTestViewSet, basename="slaughterlabtest")

app_name = "slaughter"

urlpatterns = router.urls
