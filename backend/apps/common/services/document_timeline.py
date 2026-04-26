"""
Универсальный сборщик timeline для финансовых документов
(SaleOrder / PurchaseOrder / Payment).

Объединяет:
  1. AuditLog по сущности (create / update / post / unpost / delete).
  2. Связанные платежи (для Sale/Purchase Order) с allocation на этот документ.

Возвращает list[dict] отсортированный по дате asc.
"""
from __future__ import annotations

from typing import Any, Iterable

from django.contrib.contenttypes.models import ContentType

from apps.audit.models import AuditLog


# Локализация Action.choices (плюс возможные user-friendly заголовки)
_ACTION_LABEL = {
    AuditLog.Action.CREATE: "Создание",
    AuditLog.Action.UPDATE: "Изменение",
    AuditLog.Action.DELETE: "Удаление",
    AuditLog.Action.POST: "Проведение",
    AuditLog.Action.UNPOST: "Сторнирование",
    AuditLog.Action.EXPORT: "Экспорт",
    AuditLog.Action.IMPORT: "Импорт",
    AuditLog.Action.OTHER: "Прочее",
}


def _audit_to_event(log: AuditLog) -> dict[str, Any]:
    actor = None
    if log.actor_id:
        # Берём full_name если есть, иначе email
        u = log.actor
        actor = getattr(u, "full_name", None) or getattr(u, "email", None) or str(u)
    return {
        "type": log.action,  # 'create' / 'post' / etc
        "type_label": _ACTION_LABEL.get(log.action, log.action),
        "occurred_at": log.occurred_at.isoformat() if log.occurred_at else None,
        "actor": actor,
        "title": _ACTION_LABEL.get(log.action, log.action),
        "subtitle": log.action_verb or log.entity_repr or "",
    }


def get_audit_events(entity) -> list[dict[str, Any]]:
    """Все события аудита по сущности."""
    ct = ContentType.objects.get_for_model(type(entity))
    logs = (
        AuditLog.objects
        .filter(entity_content_type=ct, entity_object_id=entity.id)
        .select_related("actor")
        .order_by("occurred_at")
    )
    return [_audit_to_event(log) for log in logs]


def get_payment_events_for_order(order) -> list[dict[str, Any]]:
    """
    События платежей по этому заказу (через PaymentAllocation с GenericFK).
    """
    from apps.payments.models import PaymentAllocation

    ct = ContentType.objects.get_for_model(type(order))
    qs = (
        PaymentAllocation.objects
        .filter(target_content_type=ct, target_object_id=order.id)
        .select_related("payment", "payment__counterparty", "payment__created_by")
    )
    events: list[dict[str, Any]] = []
    for alloc in qs:
        p = alloc.payment
        if p is None:
            continue
        actor = None
        if p.created_by_id and hasattr(p.created_by, "full_name"):
            actor = p.created_by.full_name or getattr(p.created_by, "email", None)
        events.append({
            "type": "payment",
            "type_label": "Платёж",
            "occurred_at": p.date.isoformat() if p.date else None,
            "actor": actor,
            "title": f"Платёж {p.doc_number}",
            "subtitle": (
                f"{p.get_direction_display()} · {alloc.amount_uzs} UZS"
                f" · статус: {p.get_status_display()}"
            ),
        })
    return events


def build_document_timeline(
    entity,
    *,
    extra_events: Iterable[dict[str, Any]] = (),
) -> list[dict[str, Any]]:
    """
    Собрать таймлайн для документа.

    extra_events — дополнительные события (например, платежи), уже в формате dict.
    """
    events = list(get_audit_events(entity))
    events.extend(extra_events)
    # Сортировка по occurred_at; None в конец
    events.sort(key=lambda e: e.get("occurred_at") or "9999")
    return events
