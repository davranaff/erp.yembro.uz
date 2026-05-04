from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter

from apps.common.viewsets import OrgScopedModelViewSet

from .filters import CategoryFilter, NomenclatureItemFilter, UnitFilter
from .models import Category, NomenclatureItem, Unit
from .serializers import (
    CategorySerializer,
    NomenclatureItemSerializer,
    UnitSerializer,
)


class UnitViewSet(OrgScopedModelViewSet):
    """
    /api/nomenclature/units/ — единицы измерения (кг, шт, л, доз).
    """

    serializer_class = UnitSerializer
    queryset = Unit.objects.all()
    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = UnitFilter
    ordering_fields = ["code", "name", "created_at"]
    ordering = ["code"]


class CategoryViewSet(OrgScopedModelViewSet):
    """
    /api/nomenclature/categories/ — категории номенклатуры.
    """

    serializer_class = CategorySerializer
    queryset = Category.objects.select_related("parent", "default_gl_subaccount")
    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = CategoryFilter
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]


class NomenclatureItemViewSet(OrgScopedModelViewSet):
    """
    /api/nomenclature/items/ — справочник номенклатуры.
    """

    serializer_class = NomenclatureItemSerializer
    queryset = NomenclatureItem.objects.select_related(
        "category", "unit", "default_gl_subaccount"
    )
    module_code = "core"
    required_level = "r"
    write_level = "rw"

    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_class = NomenclatureItemFilter
    ordering_fields = ["sku", "name", "created_at"]
    ordering = ["sku"]
