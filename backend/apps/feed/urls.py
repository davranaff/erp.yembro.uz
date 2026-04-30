from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FeedBatchViewSet,
    FeedLotShrinkageStateViewSet,
    FeedShrinkageProfileViewSet,
    FeedShrinkageReportView,
    ProductionTaskViewSet,
    RawMaterialBatchViewSet,
    RecipeComponentViewSet,
    RecipeVersionViewSet,
    RecipeViewSet,
)


router = DefaultRouter()
router.register(r"recipes", RecipeViewSet, basename="recipe")
router.register(r"recipe-versions", RecipeVersionViewSet, basename="recipeversion")
router.register(r"recipe-components", RecipeComponentViewSet, basename="recipecomponent")
router.register(r"raw-batches", RawMaterialBatchViewSet, basename="rawbatch")
router.register(r"production-tasks", ProductionTaskViewSet, basename="productiontask")
router.register(r"feed-batches", FeedBatchViewSet, basename="feedbatch")
router.register(
    r"shrinkage-profiles",
    FeedShrinkageProfileViewSet,
    basename="feed-shrinkage-profile",
)
router.register(
    r"shrinkage-state",
    FeedLotShrinkageStateViewSet,
    basename="feed-shrinkage-state",
)

app_name = "feed"

urlpatterns = [
    *router.urls,
    path(
        "shrinkage-report/",
        FeedShrinkageReportView.as_view(),
        name="feed-shrinkage-report",
    ),
]
