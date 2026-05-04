from rest_framework.routers import DefaultRouter

from .views import (
    IncubationRegimeDayViewSet,
    IncubationRunViewSet,
    MirageInspectionViewSet,
)


router = DefaultRouter()
router.register(r"runs", IncubationRunViewSet, basename="incubationrun")
router.register(r"regime-days", IncubationRegimeDayViewSet, basename="regimeday")
router.register(r"mirage", MirageInspectionViewSet, basename="mirageinspection")

app_name = "incubation"

urlpatterns = router.urls
