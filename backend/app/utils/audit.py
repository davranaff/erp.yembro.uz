from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID


REDACTED_AUDIT_VALUE = "***redacted***"
SENSITIVE_AUDIT_KEYS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "confirm_new_password",
        "access_token",
        "refresh_token",
        "token",
        "secret",
    }
)


def normalize_audit_value(
    value: Any,
    *,
    field_name: str | None = None,
    redact_sensitive: bool = True,
) -> Any:
    if redact_sensitive and field_name and field_name.strip().lower() in SENSITIVE_AUDIT_KEYS:
        return REDACTED_AUDIT_VALUE

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, Decimal):
        return str(value)

    if isinstance(value, (UUID, date, time, datetime)):
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key in sorted(value.keys(), key=lambda candidate: str(candidate)):
            key_text = str(key)
            normalized[key_text] = normalize_audit_value(
                value[key],
                field_name=key_text,
                redact_sensitive=redact_sensitive,
            )
        return normalized

    if isinstance(value, (list, tuple)):
        return [
            normalize_audit_value(item, redact_sensitive=redact_sensitive)
            for item in value
        ]

    if isinstance(value, set):
        return sorted(normalize_audit_value(item, redact_sensitive=redact_sensitive) for item in value)

    return str(value)


def normalize_audit_snapshot(
    value: Mapping[str, Any] | None,
    *,
    redact_sensitive: bool = True,
) -> dict[str, Any] | None:
    if value is None:
        return None
    normalized = normalize_audit_value(value, redact_sensitive=redact_sensitive)
    return normalized if isinstance(normalized, dict) else {"value": normalized}


def build_changed_fields(
    before_data: Mapping[str, Any] | None,
    after_data: Mapping[str, Any] | None,
    *,
    redact_sensitive: bool = False,
) -> list[str]:
    before_snapshot = normalize_audit_snapshot(before_data, redact_sensitive=redact_sensitive)
    after_snapshot = normalize_audit_snapshot(after_data, redact_sensitive=redact_sensitive)

    if before_snapshot is None and after_snapshot is None:
        return []
    if before_snapshot is None:
        return sorted(after_snapshot or {})
    if after_snapshot is None:
        return sorted(before_snapshot)

    changed_fields: list[str] = []
    for key in sorted(set(before_snapshot) | set(after_snapshot)):
        if before_snapshot.get(key) != after_snapshot.get(key):
            changed_fields.append(key)
    return changed_fields
