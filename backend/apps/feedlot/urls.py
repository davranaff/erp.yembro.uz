from rest_framework.routers import DefaultRouter

from .views import (
    DailyWeighingViewSet,
    FeedlotBatchViewSet,
    FeedlotFeedConsumptionViewSet,
    FeedlotMortalityViewSet,
)


router = DefaultRouter()
router.register(r"batches", FeedlotBatchViewSet, basename="feedlotbatch")
router.register(r"weighings", DailyWeighingViewSet, basename="dailyweighing")
router.register(r"feed-consumption", FeedlotFeedConsumptionViewSet, basename="feedlotfeedcons")
router.register(r"mortality", FeedlotMortalityViewSet, basename="feedlotmortality")

app_name = "feedlot"

urlpatterns = router.urls
