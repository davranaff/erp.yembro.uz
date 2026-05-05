import django_filters

from .models import PurchaseOrder


class PurchaseOrderFilter(django_filters.FilterSet):
    # Скоупим по модулю: ?module=<uuid>  ИЛИ  ?module_code=vet (удобнее)
    module_code = django_filters.CharFilter(
        field_name="module__code", lookup_expr="exact"
    )

    class Meta:
        model = PurchaseOrder
        fields = (
            "status",
            "payment_status",
            "counterparty",
            "currency",
            "module",
        )
