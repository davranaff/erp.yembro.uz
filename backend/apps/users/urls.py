from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ChangePasswordView, MeView, UserFavoritePageViewSet


app_name = "users"

router = DefaultRouter()
router.register(
    r"me/favorites",
    UserFavoritePageViewSet,
    basename="user-favorite",
)

urlpatterns = [
    path("me/", MeView.as_view(), name="me"),
    path("me/change-password/", ChangePasswordView.as_view(), name="change-password"),
] + router.urls
