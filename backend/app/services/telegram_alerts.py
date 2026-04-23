from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import inspect
import logging
from typing import Any, Mapping

from app.services.client_notifications import TelegramNotificationGateway
from app.utils.audit import normalize_audit_snapshot


logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class OperationalAlertSpec:
    resource_label: str
    module_label: str


OPERATIONAL_ALERT_SPECS: dict[str, OperationalAlertSpec] = {
    "egg_production": OperationalAlertSpec(resource_label="Производство", module_label="Маточник"),
    "egg_shipments": OperationalAlertSpec(resource_label="Отгрузки", module_label="Маточник"),
    "incubation_batches": OperationalAlertSpec(resource_label="Приход яиц", module_label="Инкубация"),
    "incubation_runs": OperationalAlertSpec(resource_label="Сортировка и вывод", module_label="Инкубация"),
    "chick_shipments": OperationalAlertSpec(resource_label="Отгрузки птенцов", module_label="Инкубация"),
    "feed_types": OperationalAlertSpec(resource_label="Типы корма", module_label="Корма"),
    "feed_ingredients": OperationalAlertSpec(resource_label="Сырьё", module_label="Корма"),
    "feed_formulas": OperationalAlertSpec(resource_label="Продукт", module_label="Корма"),
    "feed_production_batches": OperationalAlertSpec(resource_label="Выпуск продукта", module_label="Корма"),
    "feed_product_shipments": OperationalAlertSpec(resource_label="Отгрузки продукта", module_label="Корма"),
    "medicine_batches": OperationalAlertSpec(resource_label="Партии лекарств", module_label="Вет аптека"),
    "medicine_types": OperationalAlertSpec(resource_label="Типы лекарств", module_label="Вет аптека"),
    "slaughter_arrivals": OperationalAlertSpec(resource_label="Партии прихода", module_label="Убойня"),
    "slaughter_processings": OperationalAlertSpec(resource_label="Убой", module_label="Убойня"),
    "slaughter_semi_products": OperationalAlertSpec(resource_label="Разделка", module_label="Убойня"),
    "slaughter_semi_product_shipments": OperationalAlertSpec(
        resource_label="Отгрузки полуфабрикатов",
        module_label="Убойня",
    ),
    "stock_movements": OperationalAlertSpec(resource_label="Движения остатков", module_label="Операции"),
}
RECORD_LABEL_FIELDS = ("name", "title", "code", "batch_code", "invoice_no", "item_key", "id")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_snapshot(snapshot: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if snapshot is None:
        return None
    normalized = normalize_audit_snapshot(snapshot, redact_sensitive=False)
    return dict(normalized) if isinstance(normalized, dict) else None


def should_send_operational_alert(*, action: str, entity_table: str) -> bool:
    return action in {"create", "delete"} and entity_table in OPERATIONAL_ALERT_SPECS


def build_operational_alert_event(
    *,
    action: str,
    entity_table: str,
    entity_id: str,
    actor_username: str | None,
    before_data: Mapping[str, Any] | None,
    after_data: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if not should_send_operational_alert(action=action, entity_table=entity_table):
        return None

    normalized_before = _normalize_snapshot(before_data)
    normalized_after = _normalize_snapshot(after_data)
    organization_id = str(
        (normalized_after or {}).get("organization_id")
        or (normalized_before or {}).get("organization_id")
        or ""
    ).strip()
    if not organization_id:
        return None

    return {
        "action": action,
        "entity_table": entity_table,
        "entity_id": str(entity_id),
        "organization_id": organization_id,
        "actor_username": str(actor_username or "").strip() or None,
        "before_data": normalized_before,
        "after_data": normalized_after,
        "changed_at": _now_utc().isoformat(),
    }


async def _queue_operational_alert_task(payload: dict[str, Any]) -> bool:
    try:
        from app.tasks.jobs import send_telegram_admin_alert_task

        queued = send_telegram_admin_alert_task.kiq(payload)
        if inspect.isawaitable(queued):
            await queued
        return True
    except Exception as exc:  # pragma: no cover - defensive runtime guard
        logger.warning("Failed to enqueue Telegram admin alert: %s", exc)
        return False


async def enqueue_operational_admin_alert(
    *,
    action: str,
    entity_table: str,
    entity_id: str,
    actor_username: str | None,
    before_data: Mapping[str, Any] | None,
    after_data: Mapping[str, Any] | None,
) -> bool:
    payload = build_operational_alert_event(
        action=action,
        entity_table=entity_table,
        entity_id=entity_id,
        actor_username=actor_username,
        before_data=before_data,
        after_data=after_data,
    )
    if payload is None:
        return False
    return await _queue_operational_alert_task(payload)


def _coerce_mapping(value: object | None) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return dict(value)
    return None


def _resolve_record_label(snapshot: Mapping[str, Any] | None) -> str:
    data = dict(snapshot or {})
    for field_name in RECORD_LABEL_FIELDS:
        raw_value = data.get(field_name)
        value = str(raw_value or "").strip()
        if not value:
            continue
        if field_name == "id":
            return f"ID {value}"
        return value
    return "Без названия"


def _format_timestamp(raw_value: object | None) -> str:
    if isinstance(raw_value, datetime):
        value = raw_value
    else:
        try:
            value = datetime.fromisoformat(str(raw_value))
        except Exception:
            return str(raw_value or "").strip() or "-"

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


async def _resolve_organization_name(db, organization_id: str) -> str:
    row = await db.fetchrow(
        """
        SELECT name
        FROM organizations
        WHERE id = $1
        LIMIT 1
        """,
        organization_id,
    )
    return str(row["name"]).strip() if row is not None and row.get("name") is not None else organization_id


async def _resolve_department_context(
    db,
    *,
    department_id: str | None,
) -> tuple[str | None, str | None]:
    normalized_department_id = str(department_id or "").strip()
    if not normalized_department_id:
        return None, None

    row = await db.fetchrow(
        """
        SELECT
            d.name AS department_name,
            d.code AS department_code,
            dm.name AS module_name
        FROM departments AS d
        LEFT JOIN department_modules AS dm
          ON dm.key = d.module_key
        WHERE d.id = $1
        LIMIT 1
        """,
        normalized_department_id,
    )
    if row is None:
        return None, None

    department_name = str(row.get("department_name") or "").strip()
    department_code = str(row.get("department_code") or "").strip()
    module_name = str(row.get("module_name") or "").strip() or None

    if department_name and department_code:
        return f"{department_name} ({department_code})", module_name
    if department_name:
        return department_name, module_name
    if department_code:
        return department_code, module_name
    return None, module_name


async def build_operational_alert_message(db, event_payload: Mapping[str, Any]) -> str | None:
    action = str(event_payload.get("action") or "").strip().lower()
    entity_table = str(event_payload.get("entity_table") or "").strip()
    organization_id = str(event_payload.get("organization_id") or "").strip()
    if not should_send_operational_alert(action=action, entity_table=entity_table) or not organization_id:
        return None

    spec = OPERATIONAL_ALERT_SPECS[entity_table]
    snapshot = _coerce_mapping(event_payload.get("after_data") if action == "create" else event_payload.get("before_data"))
    record_label = _resolve_record_label(snapshot)
    department_label, module_label = await _resolve_department_context(
        db,
        department_id=(snapshot or {}).get("department_id"),
    )
    organization_name = await _resolve_organization_name(db, organization_id)
    effective_module_label = module_label or spec.module_label
    actor_username = str(event_payload.get("actor_username") or "").strip() or "system"
    changed_at = _format_timestamp(event_payload.get("changed_at"))

    title = "🟢 Добавлена запись" if action == "create" else "🔴 Удалена запись"
    lines = [
        title,
        f"Организация: {organization_name}",
        f"Модуль: {effective_module_label}",
        f"Отдел: {department_label or 'Не указан'}",
        f"Ресурс: {spec.resource_label}",
        f"Запись: {record_label}",
        f"Пользователь: {actor_username}",
        f"Время: {changed_at}",
    ]
    return "\n".join(lines)


async def deliver_operational_admin_alert(db, event_payload: Mapping[str, Any]) -> dict[str, Any]:
    from app.repositories.system import TelegramRecipientRepository

    organization_id = str(event_payload.get("organization_id") or "").strip()
    if not organization_id:
        return {"sent": 0, "skipped": 0, "reason": "organization_id_missing"}

    message = await build_operational_alert_message(db, event_payload)
    if not message:
        return {"sent": 0, "skipped": 0, "reason": "not_operational"}

    repository = TelegramRecipientRepository(db)
    recipients = await repository.list_active_admin_recipients(organization_id=organization_id)
    if not recipients:
        return {"sent": 0, "skipped": 0, "reason": "no_recipients"}

    gateway = TelegramNotificationGateway()
    if not gateway.is_configured:
        return {"sent": 0, "skipped": len(recipients), "reason": "gateway_not_configured"}

    sent = 0
    skipped = 0
    seen_chat_ids: set[str] = set()
    for recipient in recipients:
        chat_id = str(recipient.get("telegram_chat_id") or "").strip()
        if not chat_id or chat_id in seen_chat_ids:
            skipped += 1
            continue

        seen_chat_ids.add(chat_id)
        result = await gateway.send_message(chat_id=chat_id, text=message)
        if result.ok:
            sent += 1
        else:
            skipped += 1

    return {"sent": sent, "skipped": skipped, "reason": None}


__all__ = [
    "OPERATIONAL_ALERT_SPECS",
    "build_operational_alert_event",
    "build_operational_alert_message",
    "deliver_operational_admin_alert",
    "enqueue_operational_admin_alert",
    "should_send_operational_alert",
]
