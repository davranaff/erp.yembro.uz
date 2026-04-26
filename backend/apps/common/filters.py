"""
Переиспользуемые django-filter FilterSet-миксины.

DateRangeFilterMixin:
    В FilterSet добавляет `?date_after=` и `?date_before=` на одно поле.

IsActiveFilterMixin:
    Простой BooleanFilter на поле is_active.

CodeSearchFilterMixin:
    Объединённый поиск по code + name через `?q=`.

Использование:
    class CounterpartyFilter(DateRangeFilterMixin, django_filters.FilterSet):
        date_range_field = "created_at"

        class Meta:
            model = Counterparty
            fields = ("kind", "is_active")
"""
from __future__ import annotations

import django_filters


class DateRangeFilterMixin:
    """Добавляет `?<field>_after=` / `?<field>_before=` на date-поле."""

    date_range_field: str = "date"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        field = getattr(cls, "date_range_field", None)
        if not field:
            return
        prefix = field.rstrip("_")
        cls.base_filters = getattr(cls, "base_filters", {})
        cls.base_filters[f"{prefix}_after"] = django_filters.DateFilter(
            field_name=field, lookup_expr="gte"
        )
        cls.base_filters[f"{prefix}_before"] = django_filters.DateFilter(
            field_name=field, lookup_expr="lte"
        )


class IsActiveFilterMixin:
    """Добавляет `?is_active=` boolean-фильтр."""

    is_active_field: str = "is_active"

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        field = getattr(cls, "is_active_field", "is_active")
        cls.base_filters = getattr(cls, "base_filters", {})
        cls.base_filters["is_active"] = django_filters.BooleanFilter(
            field_name=field
        )


class CodeSearchFilterMixin:
    """
    `?q=агро` → OR-поиск по code, name (и дополнительным полям из
    search_fields_extra).
    """

    search_fields_extra: tuple[str, ...] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        extra = getattr(cls, "search_fields_extra", ())
        cls.base_filters = getattr(cls, "base_filters", {})
        cls.base_filters["q"] = django_filters.CharFilter(method="_search_q")

        def _search_q(self_filter, queryset, name, value):
            if not value:
                return queryset
            from django.db.models import Q

            q = Q(code__icontains=value) | Q(name__icontains=value)
            for extra_field in extra:
                q |= Q(**{f"{extra_field}__icontains": value})
            return queryset.filter(q)

        cls._search_q = _search_q
