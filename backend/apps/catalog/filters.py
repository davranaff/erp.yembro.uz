"""
Фильтры списка товаров для публичного API.
"""
from __future__ import annotations

import django_filters as df

from .models import Product


class ProductFilter(df.FilterSet):
    category = df.CharFilter(field_name="category__code", lookup_expr="iexact")
    brand = df.CharFilter(field_name="brand__code", lookup_expr="iexact")
    direction = df.CharFilter(field_name="direction", lookup_expr="iexact")
    protein_gte = df.NumberFilter(field_name="spec__protein_pct", lookup_expr="gte")
    protein_lte = df.NumberFilter(field_name="spec__protein_pct", lookup_expr="lte")
    age_days = df.NumberFilter(method="filter_age_days")
    is_featured = df.BooleanFilter(field_name="is_featured")

    class Meta:
        model = Product
        fields = ["category", "brand", "direction", "is_featured"]

    def filter_age_days(self, queryset, name, value):
        # Подходит товар, если возраст лежит в диапазоне age_from..age_to
        # (или одна из границ не указана).
        from django.db.models import Q

        return queryset.filter(
            (Q(age_from_days__isnull=True) | Q(age_from_days__lte=value))
            & (Q(age_to_days__isnull=True) | Q(age_to_days__gte=value)),
        )
