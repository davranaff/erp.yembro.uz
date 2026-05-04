"""
FilterSet для AuditLogViewSet.

Поддерживает диапазон по occurred_at + фильтры по actor / module / action /
сущности. Multi-select через `__in`-варианты (`action__in=create,delete`).
"""
from __future__ import annotations

import django_filters

from .models import AuditLog


class AuditLogFilter(django_filters.FilterSet):
    date_after = django_filters.IsoDateTimeFilter(
        field_name="occurred_at", lookup_expr="gte"
    )
    date_before = django_filters.IsoDateTimeFilter(
        field_name="occurred_at", lookup_expr="lte"
    )
    # Для drill-down с сущности: ?entity_content_type=N&entity_object_id=<uuid>
    entity_object_id = django_filters.UUIDFilter(field_name="entity_object_id")

    # Multi-select. Запросы вида ?action__in=create,delete&actor__in=<uuid>,<uuid>.
    # CharInFilter принимает CSV-строку и расщепляет её сам.
    action__in = django_filters.BaseInFilter(field_name="action")
    actor__in = django_filters.BaseInFilter(field_name="actor")
    module__in = django_filters.BaseInFilter(field_name="module")

    class Meta:
        model = AuditLog
        fields = (
            "module",
            "actor",
            "action",
            "entity_content_type",
            "entity_object_id",
            "date_after",
            "date_before",
            "action__in",
            "actor__in",
            "module__in",
        )
