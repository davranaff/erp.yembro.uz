from rest_framework.routers import DefaultRouter

from .views import BatchChainStepViewSet, BatchCostEntryViewSet, BatchViewSet


router = DefaultRouter()
router.register(r"batches", BatchViewSet, basename="batch")
router.register(r"batch-cost-entries", BatchCostEntryViewSet, basename="batchcostentry")
router.register(r"batch-chain-steps", BatchChainStepViewSet, basename="batchchainstep")

app_name = "batches"

urlpatterns = router.urls
