"""
Явный сервис-хелпер для записи в AuditLog.

Политика:
    - Каждый бизнес-сервис (confirm_purchase, post_payment, accept_transfer
      и т.д.) вызывает audit_log(...) в конце перед return.
    - Никаких Django signals — все side-effects явные.
    - entity_repr (snapshot __str__) фиксируется на момент события —
      переживёт удаление entity.
    - Вся функция безопасна к вызову без organization (пропустит запись,
      предупредит в лог). Бизнес-сервис никогда не должен падать из-за аудита.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ..models import AuditLog


logger = logging.getLogger(__name__)


def audit_log(
    *,
    organization,
    module=None,
    actor=None,
    action: str,
    entity=None,
    action_verb: str = "",
    diff: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: str = "",
    occurred_at=None,
) -> Optional[AuditLog]:
    """
    Записать событие в журнал аудита.

    Args:
        organization: Organization (обязательно).
        module: Module (опц.).
        actor: User (опц., для cron/system — None).
        action: AuditLog.Action choice (create/update/post/...).
        entity: любой Model instance — запишется GenericFK + __str__ snapshot.
        action_verb: человекочитаемая строка (e.g. "провёл закуп ЗК-001").
        diff: JSON с изменениями полей.
        ip_address, user_agent: из request.META.
        occurred_at: default now().

    Returns:
        AuditLog instance или None при ошибке.
    """
    if organization is None:
        logger.warning("audit_log: organization is None — запись пропущена")
        return None

    content_type = None
    object_id = None
    entity_repr = ""
    if entity is not None:
        try:
            content_type = ContentType.objects.get_for_model(type(entity))
            object_id = getattr(entity, "pk", None) or getattr(entity, "id", None)
            entity_repr = str(entity)[:255]
        except Exception as exc:
            logger.warning("audit_log: failed to resolve entity %r: %s", entity, exc)

    try:
        return AuditLog.objects.create(
            organization=organization,
            module=module,
            actor=actor,
            action=action,
            action_verb=(action_verb or "")[:64],
            entity_content_type=content_type,
            entity_object_id=object_id,
            entity_repr=entity_repr,
            ip_address=ip_address,
            user_agent=user_agent or "",
            diff=diff,
            occurred_at=occurred_at or timezone.now(),
        )
    except Exception as exc:
        # AuditLog никогда не должен ронять бизнес-сервис
        logger.exception("audit_log: failed to create AuditLog: %s", exc)
        return None
