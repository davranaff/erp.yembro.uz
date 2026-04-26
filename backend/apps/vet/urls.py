from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    SellerDeviceTokenViewSet,
    VaccinationScheduleItemViewSet,
    VaccinationScheduleViewSet,
    VetDrugViewSet,
    VetStockBatchViewSet,
    VetTreatmentLogViewSet,
)
from .views_public import VetPublicScanView, VetPublicSellView


router = DefaultRouter()
router.register(r"drugs", VetDrugViewSet, basename="vetdrug")
router.register(r"stock-batches", VetStockBatchViewSet, basename="vetstockbatch")
router.register(r"schedules", VaccinationScheduleViewSet, basename="vaccschedule")
router.register(
    r"schedule-items", VaccinationScheduleItemViewSet, basename="vaccscheduleitem"
)
router.register(r"treatments", VetTreatmentLogViewSet, basename="vettreatment")
router.register(r"seller-tokens", SellerDeviceTokenViewSet, basename="sellertoken")

app_name = "vet"

urlpatterns = router.urls + [
    path(
        "public/scan/<str:barcode>/",
        VetPublicScanView.as_view(),
        name="public-scan",
    ),
    path(
        "public/sell/",
        VetPublicSellView.as_view(),
        name="public-sell",
    ),
]
