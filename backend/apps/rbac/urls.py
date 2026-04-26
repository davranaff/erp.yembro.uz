from rest_framework.routers import DefaultRouter

from .views import (
    RolePermissionViewSet,
    RoleViewSet,
    UserModuleAccessOverrideViewSet,
    UserRoleViewSet,
)


router = DefaultRouter()
router.register(r"roles", RoleViewSet, basename="role")
router.register(r"role-permissions", RolePermissionViewSet, basename="rolepermission")
router.register(r"user-roles", UserRoleViewSet, basename="userrole")
router.register(r"overrides", UserModuleAccessOverrideViewSet, basename="override")

app_name = "rbac"

urlpatterns = router.urls
