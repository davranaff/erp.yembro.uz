import django_filters

from .models import Category, NomenclatureItem, Unit


class UnitFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="_search")

    class Meta:
        model = Unit
        fields = ("code",)

    def _search(self, qs, name, value):
        if not value:
            return qs
        return qs.filter(code__icontains=value) | qs.filter(name__icontains=value)


class CategoryFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    # Фильтр по модулю: ?module=<uuid>  ИЛИ  ?module_code=feedlot
    module_code = django_filters.CharFilter(field_name="module__code", lookup_expr="exact")

    class Meta:
        model = Category
        fields = ("parent", "module")


class NomenclatureItemFilter(django_filters.FilterSet):
    search = django_filters.CharFilter(method="_search")
    # Скоупим по модулю через связь category.module:
    #   ?module=<uuid>      — точный uuid модуля
    #   ?module_code=feedlot — код модуля (удобнее для фронта)
    module = django_filters.UUIDFilter(field_name="category__module")
    module_code = django_filters.CharFilter(
        field_name="category__module__code", lookup_expr="exact"
    )

    class Meta:
        model = NomenclatureItem
        fields = ("category", "unit", "is_active")

    def _search(self, qs, name, value):
        if not value:
            return qs
        from django.db.models import Q

        return qs.filter(
            Q(sku__icontains=value)
            | Q(name__icontains=value)
            | Q(barcode__icontains=value)
        )
