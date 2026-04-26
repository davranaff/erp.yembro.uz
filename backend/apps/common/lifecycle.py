"""
Mixin'ы для защиты CRUD-операций по статусу/lifecycle и для требования
причины удаления.

Используются на ViewSet'ах вместе с OrgScopedModelViewSet.
"""
from __future__ import annotations

from typing import Iterable

from rest_framework.exceptions import PermissionDenied, ValidationError


class ImmutableStatusMixin:
    """
    Запрещает UPDATE/PATCH/DELETE если status сущности входит в `immutable_statuses`.
    Применять к сущностям где есть финальные/проведённые состояния:
      - SlaughterShift: posted, cancelled
      - FeedlotBatch: shipped
      - IncubationRun: completed, cancelled
      - BreedingHerd: depopulated

    Использование:
        class SlaughterShiftViewSet(ImmutableStatusMixin, OrgScopedModelViewSet):
            immutable_statuses = ("posted", "cancelled")
            status_field = "status"  # default
    """

    immutable_statuses: Iterable[str] = ()
    status_field: str = "status"

    def _check_mutable(self, instance):
        status = getattr(instance, self.status_field, None)
        if status in self.immutable_statuses:
            label = getattr(instance, f"get_{self.status_field}_display", lambda: status)()
            raise PermissionDenied(
                f"Нельзя изменять или удалять записи в статусе «{label}». "
                f"Используйте reverse/cancel для отмены."
            )

    def perform_update(self, serializer):
        self._check_mutable(serializer.instance)
        super().perform_update(serializer)

    def perform_destroy(self, instance):
        self._check_mutable(instance)
        super().perform_destroy(instance)


class DeleteReasonMixin:
    """
    Требует обязательную причину при удалении (?reason=... или body.reason).
    Причина попадает в audit log как часть verb.

    Используется для дочерних записей (взвешивания, падёж, кормление, qc, lab,
    mirage), которые нужно иметь возможность удалить, но с обоснованием.
    """

    require_delete_reason: bool = True
    min_reason_length: int = 3

    def perform_destroy(self, instance):
        if not self.require_delete_reason:
            return super().perform_destroy(instance)
        request = getattr(self, "request", None)
        reason = ""
        if request is not None:
            # Из body (POST/DELETE с телом) или query param
            data = getattr(request, "data", None) or {}
            reason = (
                (data.get("reason") if isinstance(data, dict) else "")
                or request.query_params.get("reason", "")
                or ""
            ).strip()
        if len(reason) < self.min_reason_length:
            raise ValidationError({
                "reason": (
                    f"Укажите причину удаления (мин. {self.min_reason_length} симв.) "
                    f"в body или ?reason=..."
                )
            })
        # Прокидываем причину в audit (через action_verb override)
        self._delete_reason = reason
        super().perform_destroy(instance)

    def _audit_verb_for_delete(self, instance) -> str:
        reason = getattr(self, "_delete_reason", "")
        base = f"delete {type(instance).__name__} {instance}"
        return f"{base} · reason: {reason}" if reason else base
