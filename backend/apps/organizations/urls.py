from rest_framework.routers import DefaultRouter

from .views import OrganizationMembershipViewSet, OrganizationViewSet


router = DefaultRouter()
router.register(r"organizations", OrganizationViewSet, basename="organization")
router.register(r"memberships", OrganizationMembershipViewSet, basename="membership")

app_name = "organizations"

urlpatterns = router.urls
