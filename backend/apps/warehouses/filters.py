import django_filters

from .models import ProductionBlock, StockMovement, Warehouse


class ProductionBlockFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="_search")
    # Удобный фильтр по коду модуля: ?module_code=feedlot (вместо ?module=<uuid>)
    module_code = django_filters.CharFilter(
        field_name="module__code", lookup_expr="exact"
    )

    class Meta:
        model = ProductionBlock
        fields = ("module", "kind", "is_active")

    def _search(self, qs, name, value):
        if not value:
            return qs
        from django.db.models import Q

        return qs.filter(Q(code__icontains=value) | Q(name__icontains=value))


class WarehouseFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="_search")
    module_code = django_filters.CharFilter(
        field_name="module__code", lookup_expr="exact"
    )

    class Meta:
        model = Warehouse
        fields = ("module", "production_block", "is_active")

    def _search(self, qs, name, value):
        if not value:
            return qs
        from django.db.models import Q

        return qs.filter(Q(code__icontains=value) | Q(name__icontains=value))


class StockMovementFilter(django_filters.FilterSet):
    date_after = django_filters.DateTimeFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateTimeFilter(field_name="date", lookup_expr="lte")
    # Удобные фильтры
    module_code = django_filters.CharFilter(
        field_name="module__code", lookup_expr="exact"
    )
    batch_doc = django_filters.CharFilter(
        field_name="batch__doc_number", lookup_expr="icontains"
    )
    # Единый фильтр «склад» — ищет движения где склад фигурирует
    # либо как источник (OUTGOING), либо как получатель (INCOMING).
    # Без этого пользователь, фильтруя «По складу X», видит только OUTGOING
    # и пропускает оприходования (приёмки, расфасовка, transfer in).
    warehouse = django_filters.UUIDFilter(method="filter_warehouse")

    def filter_warehouse(self, qs, name, value):
        return qs.filter(Q(warehouse_from=value) | Q(warehouse_to=value))

    class Meta:
        model = StockMovement
        fields = (
            "module",
            "kind",
            "nomenclature",
            "warehouse_from",
            "warehouse_to",
            "counterparty",
            "batch",
        )
