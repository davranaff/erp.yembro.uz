from rest_framework.routers import DefaultRouter

from .views import PaymentViewSet


router = DefaultRouter()
router.register(r"", PaymentViewSet, basename="payment")

app_name = "payments"

urlpatterns = router.urls
