from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, NomenclatureItemViewSet, UnitViewSet


router = DefaultRouter()
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"items", NomenclatureItemViewSet, basename="item")

app_name = "nomenclature"

urlpatterns = router.urls
