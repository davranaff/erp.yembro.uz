from rest_framework.routers import DefaultRouter

from .views import (
    BreedingFeedConsumptionViewSet,
    BreedingHerdViewSet,
    BreedingMortalityViewSet,
    DailyEggProductionViewSet,
)


router = DefaultRouter()
router.register(r"herds", BreedingHerdViewSet, basename="herd")
router.register(r"daily-egg", DailyEggProductionViewSet, basename="dailyegg")
router.register(r"mortality", BreedingMortalityViewSet, basename="mortality")
router.register(r"feed-consumption", BreedingFeedConsumptionViewSet, basename="feedconsumption")

app_name = "matochnik"

urlpatterns = router.urls
