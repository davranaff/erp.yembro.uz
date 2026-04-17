from __future__ import annotations

from datetime import date, timedelta
import re
import uuid
from typing import Any

from httpx import AsyncClient


AUDIT_FIELDS = {"id", "created_at", "updated_at", "deleted_at"}
UNIQUE_STRING_FIELDS = {
    "name",
    "legal_name",
    "code",
    "key",
    "title",
    "slug",
    "organization_key",
    "client_code",
    "email",
    "phone",
    "invoice_no",
    "lot_no",
    "batch_code",
    "barcode",
    "description",
    "part_name",
}
TEST_EMPLOYEE_ID = "70111111-1111-1111-1111-111111111111"
DATE_SUFFIXES = ("_date", "_on", "_start", "_end")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
DATE_FIELDS = {
    "month_start",
    "produced_on",
    "shipped_on",
    "expense_date",
    "arrived_on",
    "start_date",
    "finished_on",
    "started_on",
    "processed_on",
    "expiry_date",
}


def make_auth_headers(permission_prefix: str, role: str = "admin") -> dict[str, str]:
    all_permissions = ",".join(
        [
            f"{permission_prefix}.read",
            f"{permission_prefix}.list",
            f"{permission_prefix}.create",
            f"{permission_prefix}.write",
            f"{permission_prefix}.update",
            f"{permission_prefix}.delete",
        ]
    )
    return {
        "X-Employee-Id": TEST_EMPLOYEE_ID,
        "X-Roles": role,
        "X-Permissions": all_permissions,
    }


def make_forbidden_headers() -> dict[str, str]:
    return {
        "X-Employee-Id": TEST_EMPLOYEE_ID,
        "X-Roles": "viewer",
        "X-Permissions": "other.resource",
    }


def make_admin_headers() -> dict[str, str]:
    return {
        "X-Employee-Id": TEST_EMPLOYEE_ID,
        "X-Roles": "admin",
        "X-Permissions": "",
    }


def extract_data(response) -> Any:
    payload = response.json()
    assert payload["ok"] is True, payload
    return payload["data"]


def _suffix_string(value: str, token: str) -> str:
    if "@" in value:
        local, domain = value.split("@", 1)
        return f"{local}+{token}@{domain}"
    return f"{value}-{token}"


def _shift_date_string(value: str, offset_days: int = 32) -> str:
    shifted = date.fromisoformat(value) + timedelta(days=offset_days)
    return shifted.isoformat()


def _clone_value(key: str, value: Any, token: str) -> Any:
    if value is None:
        return None

    if isinstance(value, str):
        if key in DATE_FIELDS or key.endswith(DATE_SUFFIXES):
            return _shift_date_string(value)
        if key in UNIQUE_STRING_FIELDS:
            return _suffix_string(value, token)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return _shift_date_string(value)
        return value

    return value


async def _list_items(api_client: AsyncClient, path: str) -> list[dict[str, Any]]:
    response = await api_client.get(path, headers=make_admin_headers())
    assert response.status_code == 200
    return list(extract_data(response)["items"])


async def _pick_alternative_id(
    api_client: AsyncClient,
    path: str,
    current_id: str,
    organization_id: str | None = None,
) -> str:
    items = await _list_items(api_client, path)
    for item in items:
        item_id = str(item.get("id", ""))
        if not item_id or item_id == current_id:
            continue
        if organization_id and str(item.get("organization_id", "")) != organization_id:
            continue
        return item_id
    raise AssertionError(f"Could not find alternative related record for {path}")


async def build_create_payload(api_client: AsyncClient, path: str) -> dict[str, Any]:
    items = await _list_items(api_client, path)
    assert items, f"No fixture data available for {path}"

    token = uuid.uuid4().hex[:8]
    template = dict(items[0])
    payload: dict[str, Any] = {
        key: _clone_value(key, value, token)
        for key, value in template.items()
        if key not in AUDIT_FIELDS
    }
    payload["id"] = str(uuid.uuid4())

    if path.endswith("/feed/formula-ingredients"):
        payload["ingredient_id"] = await _pick_alternative_id(
            api_client,
            "/api/v1/feed/ingredients",
            str(template["ingredient_id"]),
            str(template.get("organization_id", "")) or None,
        )

    if path.endswith("/feed/raw-consumptions"):
        payload["ingredient_id"] = await _pick_alternative_id(
            api_client,
            "/api/v1/feed/ingredients",
            str(template["ingredient_id"]),
            str(template.get("organization_id", "")) or None,
        )

    if path.endswith("/core/currencies"):
        payload["code"] = f"C{token[:7]}".upper()
        payload["name"] = f"Test currency {token}"
        payload["symbol"] = token[:4].upper()

    if path.endswith("/core/departments"):
        payload["parent_department_id"] = str(template["id"])
        payload["module_key"] = str(template["module_key"])
        payload["organization_id"] = str(template["organization_id"])

    if path.endswith("/hr/employees") and not str(payload.get("password") or "").strip():
        payload["password"] = f"TempPass-{token}!"
    if path.endswith("/hr/employees"):
        # Non-admin actors are forbidden to assign roles on employee create.
        # Access-control tests validate CRUD permissions, not HR security policies.
        payload.pop("role_ids", None)

    if path.endswith("/hr/roles"):
        # Non-admin actors are forbidden to assign permissions on role create.
        payload.pop("permission_ids", None)

    if path.endswith("/incubation/chick-arrivals"):
        # Keep generated payload safely within remaining stock limits.
        payload["chicks_count"] = 1

    return payload


def build_update_payload(record: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "is_active",
        "notes",
        "note",
        "purpose",
        "description",
        "title",
        "name",
        "code",
        "slug",
        "invoice_no",
        "lot_no",
        "batch_code",
        "barcode",
    ):
        if key not in record:
            continue
        value = record[key]
        if key == "is_active" and isinstance(value, bool):
            return {key: not value}
        if value is None and key in {"notes", "note", "purpose", "description"}:
            return {key: "Updated by integration test"}
        if isinstance(value, str) and value:
            if key == "code" and len(value) <= 8:
                return {key: f"U{uuid.uuid4().hex[:7]}".upper()}
            return {key: f"{value}-updated"}

    for key, value in record.items():
        if key in AUDIT_FIELDS or key.endswith("_id"):
            continue
        if isinstance(value, bool):
            return {key: not value}
        if isinstance(value, (int, float)):
            return {key: value + 1}
        if isinstance(value, str) and UUID_RE.fullmatch(value):
            continue
        if isinstance(value, str) and (key in DATE_FIELDS or key.endswith(DATE_SUFFIXES)):
            return {key: _shift_date_string(value)}
        if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            return {key: _shift_date_string(value)}
        if isinstance(value, str) and value:
            return {key: f"{value}-updated"}

    raise AssertionError("Could not determine a safe update payload")


async def run_crud_flow(api_client: AsyncClient, path: str, permission_prefix: str) -> None:
    response = await api_client.get(path)
    assert response.status_code == 401

    response = await api_client.get(path, headers=make_forbidden_headers())
    assert response.status_code == 403

    headers = make_auth_headers(permission_prefix)
    create_payload = await build_create_payload(api_client, path)
    entity_id = str(create_payload["id"])

    response = await api_client.post(path, json=create_payload, headers=headers)
    assert response.status_code == 201
    created_record = extract_data(response)
    assert created_record["id"] == entity_id

    response = await api_client.get(path, headers=headers)
    assert response.status_code == 200
    list_data = extract_data(response)
    assert list_data["total"] >= 1
    assert any(item["id"] == entity_id for item in list_data["items"])

    response = await api_client.get(f"{path}/{entity_id}", headers=headers)
    assert response.status_code == 200
    fetched_record = extract_data(response)
    assert fetched_record["id"] == entity_id

    update_payload = build_update_payload(fetched_record)

    response = await api_client.put(f"{path}/{entity_id}", json=update_payload, headers=headers)
    assert response.status_code == 200
    updated_record = extract_data(response)
    assert updated_record["id"] == entity_id
    for key, value in update_payload.items():
        assert updated_record[key] == value

    response = await api_client.delete(f"{path}/{entity_id}", headers=headers)
    assert response.status_code == 200
    delete_data = extract_data(response)
    assert delete_data["deleted"] is True

    response = await api_client.get(f"{path}/{entity_id}", headers=headers)
    assert response.status_code == 404


async def assert_delete_conflict(
    api_client: AsyncClient,
    path: str,
    permission_prefix: str,
    entity_id: str,
) -> None:
    headers = make_auth_headers(permission_prefix)
    response = await api_client.delete(f"{path}/{entity_id}", headers=headers)
    assert response.status_code == 409
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "conflict_error"
