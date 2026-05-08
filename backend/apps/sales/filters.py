from __future__ import annotations

import django_filters

from .models import SaleOrder


class SaleOrderFilter(django_filters.FilterSet):
    """
    Фильтры списка продаж: helpful date-range алиасы поверх стандартных
    filterset_fields. Frontend шлёт `date_after` / `date_before` —
    они конвертируются в `date__gte` / `date__lte`.
    """

    date_after = django_filters.DateFilter(field_name="date", lookup_expr="gte")
    date_before = django_filters.DateFilter(field_name="date", lookup_expr="lte")

    class Meta:
        model = SaleOrder
        fields = ("status", "payment_status", "customer", "currency", "module")
