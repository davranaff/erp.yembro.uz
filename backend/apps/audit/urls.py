from rest_framework.routers import DefaultRouter

from .views import AuditLogViewSet


router = DefaultRouter()
router.register(r"", AuditLogViewSet, basename="auditlog")

app_name = "audit"

urlpatterns = router.urls
