from rest_framework.routers import DefaultRouter

from .views import ModuleViewSet, OrganizationModuleViewSet


router = DefaultRouter()
router.register(r"modules", ModuleViewSet, basename="module")
router.register(r"organization-modules", OrganizationModuleViewSet, basename="orgmodule")

app_name = "modules"

urlpatterns = router.urls
