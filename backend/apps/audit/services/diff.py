"""
Хелперы для записи «до/после» в AuditLog.diff.

Политика:
- snapshot_model(instance, fields) → dict с примитивами (json-serializable).
  FK сворачиваются в id (UUID/int → str), Decimal → str, datetime → ISO.
- compute_diff(before, after) → dict вида {field: {"before": x, "after": y}}
  только для полей, где значение реально поменялось.
- Для create: передавай before=None — diff будет {"_created": after_snapshot}.
- Для delete: передавай after=None — diff будет {"_deleted": before_snapshot}.

Цель — компактный JSON, не дублирующий неизменённые поля. Удобно для
ui-рендеринга «status: DRAFT → CONFIRMED, paid_amount_uzs: 0 → 100000».
"""
from __future__ import annotations

import datetime
import decimal
import uuid
from typing import Any, Iterable, Optional


def _serialize(value: Any) -> Any:
    """Привести значение к json-сериализуемому виду."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, decimal.Decimal):
        # Decimal → str, чтобы не терять precision (json не имеет Decimal)
        return str(value)
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)):
        return value.isoformat()
    # Django Model — возьмём pk
    pk = getattr(value, "pk", None)
    if pk is not None:
        return str(pk)
    return str(value)


def snapshot_model(
    instance,
    fields: Optional[Iterable[str]] = None,
) -> dict[str, Any]:
    """
    Снять плоский снапшот полей инстанса.

    Args:
        instance: Django Model
        fields: явный список полей. Если None — берём все concrete-поля
            модели (без m2m и reverse-relations).

    Returns:
        dict {field_name: serialized_value}. FK сериализуются как
        '<field>_id' → str(pk), чтобы diff показывал именно изменение
        связи, а не магический repr.
    """
    if instance is None:
        return {}

    if fields is None:
        meta_fields = [
            f for f in instance._meta.get_fields()
            if getattr(f, "concrete", False) and not f.many_to_many
        ]
        names: list[str] = []
        for f in meta_fields:
            # для FK сохраняем «<name>_id» — компактнее и stable.
            if f.is_relation and getattr(f, "many_to_one", False):
                names.append(f.attname)  # e.g. "warehouse_id"
            else:
                names.append(f.name)
    else:
        names = list(fields)

    out: dict[str, Any] = {}
    for name in names:
        try:
            value = getattr(instance, name, None)
        except Exception:
            continue
        out[name] = _serialize(value)
    return out


def compute_diff(
    before: Optional[dict[str, Any]],
    after: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """
    Сравнить два снапшота, вернуть только изменённые поля.

    Семантика:
        - before=None, after=dict → {"_created": after}
        - before=dict, after=None → {"_deleted": before}
        - оба dict → {field: {"before": x, "after": y}} для разных пар

    Returns:
        dict, пустой если изменений нет.
    """
    if before is None and after is None:
        return {}
    if before is None:
        return {"_created": dict(after or {})}
    if after is None:
        return {"_deleted": dict(before)}

    changes: dict[str, Any] = {}
    keys = set(before) | set(after)
    for k in keys:
        b = before.get(k)
        a = after.get(k)
        if b == a:
            continue
        changes[k] = {"before": b, "after": a}
    return changes
