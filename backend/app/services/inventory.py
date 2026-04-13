from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.core.exceptions import ValidationError
from app.repositories.core import WarehouseRepository
from app.repositories.inventory import StockMovementRepository
from app.schemas.inventory import StockMovementReadSchema
from app.services.base import BaseService


PLUS_MOVEMENTS = {"incoming", "transfer_in", "adjustment_in"}
MINUS_MOVEMENTS = {"outgoing", "transfer_out", "adjustment_out"}
ITEM_TYPES = {"egg", "chick", "feed", "medicine", "semi_product"}
ITEM_KEY_REFERENCE_TABLE = "__inventory_item_key__"


@dataclass(slots=True)
class StockMovementDraft:
    organization_id: str
    department_id: str | None
    item_type: str
    item_key: str
    movement_kind: str
    quantity: Decimal
    unit: str
    occurred_on: date
    reference_table: str
    reference_id: str
    warehouse_id: str | None = None
    note: str | None = None
    counterparty_department_id: str | None = None
    counterparty_warehouse_id: str | None = None


def normalize_stock_movement_unit(raw_value: object | None) -> str:
    normalized = str(raw_value or "").strip().lower()
    if not normalized:
        return "pcs"
    if normalized in {"pcs", "piece", "pieces", "шт", "dona"}:
        return "pcs"
    if normalized in {"kg", "kgs", "кг"}:
        return "kg"
    if normalized in {"ltr", "litr", "liter", "litre", "l"}:
        return "ltr"
    raise ValidationError("unit must be one of: pcs, kg, ltr")


def _build_static_reference_options(values: list[str]) -> list[dict[str, str]]:
    return [{"value": value, "label": value} for value in values]


def _compose_option_label(*parts: object | None) -> str:
    return " · ".join(str(part).strip() for part in parts if str(part or "").strip())


async def _fetch_scoped_item_keys_from_movements(
    *,
    db,
    organization_id: str,
    item_type: str,
    department_id: str | None = None,
) -> list[str]:
    params: list[object] = [organization_id, item_type]
    clauses = [
        "organization_id = $1",
        "item_type = $2",
    ]
    if department_id:
        params.append(department_id)
        clauses.append(f"department_id = ${len(params)}")

    rows = await db.fetch(
        f"""
        SELECT DISTINCT item_key
        FROM stock_movements
        WHERE {' AND '.join(clauses)}
        ORDER BY item_key ASC
        """,
        *params,
    )
    return [str(row["item_key"]).strip() for row in rows if str(row["item_key"]).strip()]


async def _resolve_inventory_item_key_option(
    *,
    db,
    item_type: str,
    item_key: str,
) -> dict[str, str] | None:
    normalized_item_type = str(item_type or "").strip().lower()
    normalized_item_key = str(item_key or "").strip()
    if normalized_item_type == "egg" and normalized_item_key.startswith("egg:"):
        entity_id = normalized_item_key.split(":", 1)[1]
        row = await db.fetchrow(
            """
            SELECT ep.id, ep.produced_on, d.name AS department_name
            FROM egg_production AS ep
            LEFT JOIN departments AS d ON d.id = ep.department_id
            WHERE ep.id::text = $1
            LIMIT 1
            """,
            entity_id,
        )
        if row is not None:
            return {
                "value": normalized_item_key,
                "label": _compose_option_label("Egg production", row["produced_on"], row["department_name"]),
            }

    if normalized_item_type == "chick":
        if normalized_item_key.startswith("chick_run:"):
            entity_id = normalized_item_key.split(":", 1)[1]
            row = await db.fetchrow(
                """
                SELECT ir.id, ir.start_date, d.name AS department_name
                FROM incubation_runs AS ir
                LEFT JOIN departments AS d ON d.id = ir.department_id
                WHERE ir.id::text = $1
                LIMIT 1
                """,
                entity_id,
            )
            if row is not None:
                return {
                    "value": normalized_item_key,
                    "label": _compose_option_label("Incubation run", row["start_date"], row["department_name"]),
                }
        if normalized_item_key.startswith("chick_arrival:"):
            entity_id = normalized_item_key.split(":", 1)[1]
            row = await db.fetchrow(
                """
                SELECT ca.id, ca.arrived_on, d.name AS department_name
                FROM chick_arrivals AS ca
                LEFT JOIN departments AS d ON d.id = ca.department_id
                WHERE ca.id::text = $1
                LIMIT 1
                """,
                entity_id,
            )
            if row is not None:
                return {
                    "value": normalized_item_key,
                    "label": _compose_option_label("Chick arrival", row["arrived_on"], row["department_name"]),
                }

    if normalized_item_type == "feed":
        if normalized_item_key.startswith("feed_product:"):
            entity_id = normalized_item_key.split(":", 1)[1]
            row = await db.fetchrow(
                """
                SELECT id, name, code
                FROM feed_types
                WHERE id::text = $1
                LIMIT 1
                """,
                entity_id,
            )
            if row is not None:
                return {
                    "value": normalized_item_key,
                    "label": _compose_option_label("Feed product", f"{row['name']} ({row['code']})"),
                }
        if normalized_item_key.startswith("feed_raw:"):
            entity_id = normalized_item_key.split(":", 1)[1]
            row = await db.fetchrow(
                """
                SELECT id, name, code
                FROM feed_ingredients
                WHERE id::text = $1
                LIMIT 1
                """,
                entity_id,
            )
            if row is not None:
                return {
                    "value": normalized_item_key,
                    "label": _compose_option_label("Feed ingredient", f"{row['name']} ({row['code']})"),
                }

    if normalized_item_type == "medicine" and normalized_item_key.startswith("medicine_batch:"):
        entity_id = normalized_item_key.split(":", 1)[1]
        row = await db.fetchrow(
            """
            SELECT
                mb.id,
                mb.batch_code,
                mt.name AS medicine_name,
                d.name AS department_name
            FROM medicine_batches AS mb
            LEFT JOIN medicine_types AS mt ON mt.id = mb.medicine_type_id
            LEFT JOIN departments AS d ON d.id = mb.department_id
            WHERE mb.id::text = $1
            LIMIT 1
            """,
            entity_id,
        )
        if row is not None:
            return {
                "value": normalized_item_key,
                "label": _compose_option_label(
                    "Medicine batch",
                    row["medicine_name"] or row["batch_code"],
                    row["batch_code"],
                    row["department_name"],
                ),
            }

    if normalized_item_type == "semi_product" and normalized_item_key.startswith("semi_product:"):
        entity_id = normalized_item_key.split(":", 1)[1]
        row = await db.fetchrow(
            """
            SELECT sp.id, sp.code, sp.part_name, d.name AS department_name
            FROM slaughter_semi_products AS sp
            LEFT JOIN departments AS d ON d.id = sp.department_id
            WHERE sp.id::text = $1
            LIMIT 1
            """,
            entity_id,
        )
        if row is not None:
            return {
                "value": normalized_item_key,
                "label": _compose_option_label(
                    "Semi-product",
                    row["part_name"] or row["code"],
                    row["code"],
                    row["department_name"],
                ),
            }

    return None


def _finalize_item_key_options(
    options: list[dict[str, str]],
    *,
    search: str | None = None,
    values: list[str] | None = None,
    limit: int = 25,
) -> list[dict[str, str]]:
    normalized_search = str(search or "").strip().lower()
    normalized_values = [str(value).strip() for value in (values or []) if str(value).strip()]

    unique_options: list[dict[str, str]] = []
    option_by_value: dict[str, dict[str, str]] = {}
    for option in options:
        value = str(option.get("value") or "").strip()
        if not value or value in option_by_value:
            continue
        normalized_option = {
            "value": value,
            "label": str(option.get("label") or value).strip() or value,
        }
        option_by_value[value] = normalized_option
        unique_options.append(normalized_option)

    def matches(option: dict[str, str]) -> bool:
        if not normalized_search:
            return True
        haystack = f"{option['label']} {option['value']}".lower()
        return normalized_search in haystack

    pinned_options: list[dict[str, str]] = []
    seen_values: set[str] = set()
    for value in normalized_values:
        option = option_by_value.get(value)
        if option is None:
            continue
        pinned_options.append(option)
        seen_values.add(value)

    filtered_options = sorted(
        (
            option
            for option in unique_options
            if option["value"] not in seen_values and matches(option)
        ),
        key=lambda option: (option["label"].lower(), option["value"]),
    )
    return (pinned_options + filtered_options)[: max(limit, len(pinned_options))]


async def _fetch_inventory_item_key_options(
    *,
    db,
    organization_id: str,
    item_type: str,
    department_id: str | None = None,
    search: str | None = None,
    values: list[str] | None = None,
    limit: int = 25,
) -> list[dict[str, str]]:
    normalized_item_type = str(item_type or "").strip().lower()
    normalized_department_id = str(department_id or "").strip() or None
    if normalized_item_type not in ITEM_TYPES:
        return []

    options: list[dict[str, str]] = []

    if normalized_item_type == "egg":
        params: list[object] = [organization_id]
        clauses = ["ep.organization_id = $1"]
        if normalized_department_id:
            params.append(normalized_department_id)
            clauses.append(f"ep.department_id = ${len(params)}")
        rows = await db.fetch(
            f"""
            SELECT ep.id, ep.produced_on, d.name AS department_name
            FROM egg_production AS ep
            LEFT JOIN departments AS d ON d.id = ep.department_id
            WHERE {' AND '.join(clauses)}
            ORDER BY ep.produced_on DESC, ep.id DESC
            """,
            *params,
        )
        options = [
            {
                "value": f"egg:{row['id']}",
                "label": _compose_option_label("Egg production", row["produced_on"], row["department_name"]),
            }
            for row in rows
        ]

    if normalized_item_type == "chick":
        run_params: list[object] = [organization_id]
        run_clauses = ["ir.organization_id = $1"]
        arrival_params: list[object] = [organization_id]
        arrival_clauses = ["ca.organization_id = $1"]
        if normalized_department_id:
            run_params.append(normalized_department_id)
            run_clauses.append(f"ir.department_id = ${len(run_params)}")
            arrival_params.append(normalized_department_id)
            arrival_clauses.append(f"ca.department_id = ${len(arrival_params)}")

        run_rows = await db.fetch(
            f"""
            SELECT ir.id, ir.start_date, d.name AS department_name
            FROM incubation_runs AS ir
            LEFT JOIN departments AS d ON d.id = ir.department_id
            WHERE {' AND '.join(run_clauses)}
            ORDER BY ir.start_date DESC, ir.id DESC
            """,
            *run_params,
        )
        arrival_rows = await db.fetch(
            f"""
            SELECT ca.id, ca.arrived_on, d.name AS department_name
            FROM chick_arrivals AS ca
            LEFT JOIN departments AS d ON d.id = ca.department_id
            WHERE {' AND '.join(arrival_clauses)}
            ORDER BY ca.arrived_on DESC, ca.id DESC
            """,
            *arrival_params,
        )
        options = [
            {
                "value": f"chick_run:{row['id']}",
                "label": _compose_option_label("Incubation run", row["start_date"], row["department_name"]),
            }
            for row in run_rows
        ] + [
            {
                "value": f"chick_arrival:{row['id']}",
                "label": _compose_option_label("Chick arrival", row["arrived_on"], row["department_name"]),
            }
            for row in arrival_rows
        ]

    if normalized_item_type == "feed":
        product_rows = await db.fetch(
            """
            SELECT id, name, code
            FROM feed_types
            WHERE organization_id = $1
            ORDER BY name ASC, code ASC, id ASC
            """,
            organization_id,
        )
        ingredient_rows = await db.fetch(
            """
            SELECT id, name, code
            FROM feed_ingredients
            WHERE organization_id = $1
            ORDER BY name ASC, code ASC, id ASC
            """,
            organization_id,
        )
        options = [
            {
                "value": f"feed_product:{row['id']}",
                "label": _compose_option_label("Feed product", f"{row['name']} ({row['code']})"),
            }
            for row in product_rows
        ] + [
            {
                "value": f"feed_raw:{row['id']}",
                "label": _compose_option_label("Feed ingredient", f"{row['name']} ({row['code']})"),
            }
            for row in ingredient_rows
        ]

    if normalized_item_type == "medicine":
        params = [organization_id]
        clauses = ["mb.organization_id = $1"]
        if normalized_department_id:
            params.append(normalized_department_id)
            clauses.append(f"mb.department_id = ${len(params)}")
        rows = await db.fetch(
            f"""
            SELECT
                mb.id,
                mb.batch_code,
                mb.arrived_on,
                mt.name AS medicine_name,
                d.name AS department_name
            FROM medicine_batches AS mb
            LEFT JOIN medicine_types AS mt ON mt.id = mb.medicine_type_id
            LEFT JOIN departments AS d ON d.id = mb.department_id
            WHERE {' AND '.join(clauses)}
            ORDER BY mb.arrived_on DESC, mb.batch_code ASC, mb.id DESC
            """,
            *params,
        )
        options = [
            {
                "value": f"medicine_batch:{row['id']}",
                "label": _compose_option_label(
                    "Medicine batch",
                    row["medicine_name"] or row["batch_code"],
                    row["batch_code"],
                    row["department_name"],
                ),
            }
            for row in rows
        ]

    if normalized_item_type == "semi_product":
        params = [organization_id]
        clauses = ["sp.organization_id = $1"]
        if normalized_department_id:
            params.append(normalized_department_id)
            clauses.append(f"sp.department_id = ${len(params)}")
        rows = await db.fetch(
            f"""
            SELECT sp.id, sp.code, sp.part_name, d.name AS department_name
            FROM slaughter_semi_products AS sp
            LEFT JOIN departments AS d ON d.id = sp.department_id
            WHERE {' AND '.join(clauses)}
            ORDER BY COALESCE(sp.part_name, sp.code) ASC, sp.code ASC, sp.id ASC
            """,
            *params,
        )
        options = [
            {
                "value": f"semi_product:{row['id']}",
                "label": _compose_option_label(
                    "Semi-product",
                    row["part_name"] or row["code"],
                    row["code"],
                    row["department_name"],
                ),
            }
            for row in rows
        ]

    if normalized_department_id:
        scoped_item_keys = await _fetch_scoped_item_keys_from_movements(
            db=db,
            organization_id=organization_id,
            item_type=normalized_item_type,
            department_id=normalized_department_id,
        )
        existing_values = {str(option["value"]).strip() for option in options}
        for scoped_item_key in scoped_item_keys:
            if scoped_item_key in existing_values:
                continue
            resolved_option = await _resolve_inventory_item_key_option(
                db=db,
                item_type=normalized_item_type,
                item_key=scoped_item_key,
            )
            options.append(
                resolved_option
                or {
                    "value": scoped_item_key,
                    "label": scoped_item_key,
                }
            )
            existing_values.add(scoped_item_key)

    return _finalize_item_key_options(
        options,
        search=search,
        values=values,
        limit=limit,
    )


async def _inventory_item_key_exists(
    *,
    db,
    organization_id: str,
    item_type: str,
    item_key: str,
    department_id: str | None = None,
) -> bool:
    normalized_item_key = str(item_key or "").strip()
    if not normalized_item_key:
        return False

    options = await _fetch_inventory_item_key_options(
        db=db,
        organization_id=organization_id,
        item_type=item_type,
        department_id=department_id,
        values=[normalized_item_key],
        limit=1,
    )
    return any(option["value"] == normalized_item_key for option in options)


class StockLedgerService:
    def __init__(
        self,
        repository: StockMovementRepository,
        warehouse_repository: WarehouseRepository | None = None,
    ) -> None:
        self.repository = repository
        self.warehouse_repository = warehouse_repository or WarehouseRepository(repository.db)

    @staticmethod
    def _to_decimal(raw_value: object) -> Decimal:
        if isinstance(raw_value, Decimal):
            value = raw_value
        else:
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, ValueError, TypeError) as exc:
                raise ValidationError("quantity has an invalid value") from exc
        if value <= 0:
            raise ValidationError("quantity must be positive")
        return value.quantize(Decimal("0.001"))

    async def get_balance(
        self,
        *,
        organization_id: str,
        department_id: str | None,
        warehouse_id: str | None = None,
        item_type: str,
        item_key: str,
        as_of: date | None = None,
    ) -> Decimal:
        resolved_department_id = self._normalize_scope_value(department_id)
        resolved_warehouse_id = self._normalize_scope_value(warehouse_id)
        if resolved_warehouse_id:
            resolved_scope = await self._resolve_scope(
                organization_id=organization_id,
                department_id=resolved_department_id,
                warehouse_id=resolved_warehouse_id,
                require_warehouse=True,
            )
            resolved_department_id = resolved_scope["department_id"]
            resolved_warehouse_id = resolved_scope["warehouse_id"]
        elif resolved_department_id:
            await self._resolve_scope(
                organization_id=organization_id,
                department_id=resolved_department_id,
                require_warehouse=False,
            )
        else:
            raise ValidationError("department_id or warehouse_id is required")

        return await self.repository.get_balance(
            organization_id=organization_id,
            warehouse_id=resolved_warehouse_id,
            department_id=resolved_department_id,
            item_type=item_type,
            item_key=item_key,
            as_of=as_of,
        )

    async def list_balances(
        self,
        *,
        organization_id: str,
        department_id: str | None,
        warehouse_id: str | None = None,
        item_type: str,
        as_of: date | None = None,
    ) -> list[dict[str, object]]:
        resolved_department_id = self._normalize_scope_value(department_id)
        resolved_warehouse_id = self._normalize_scope_value(warehouse_id)
        if resolved_warehouse_id:
            resolved_scope = await self._resolve_scope(
                organization_id=organization_id,
                department_id=resolved_department_id,
                warehouse_id=resolved_warehouse_id,
                require_warehouse=True,
            )
            resolved_department_id = resolved_scope["department_id"]
            resolved_warehouse_id = resolved_scope["warehouse_id"]
        elif resolved_department_id:
            await self._resolve_scope(
                organization_id=organization_id,
                department_id=resolved_department_id,
                require_warehouse=False,
            )
        else:
            raise ValidationError("department_id or warehouse_id is required")

        rows = await self.repository.list_balances(
            organization_id=organization_id,
            warehouse_id=resolved_warehouse_id,
            department_id=resolved_department_id,
            item_type=item_type,
            as_of=as_of,
        )
        normalized_rows: list[dict[str, object]] = []
        for row in rows:
            normalized_rows.append(
                {
                    "item_type": row.get("item_type"),
                    "item_key": row.get("item_key"),
                    "balance": str(Decimal(str(row.get("balance") or 0)).quantize(Decimal("0.001"))),
                    "unit": row.get("unit"),
                    "last_movement_on": row.get("last_movement_on"),
                }
            )
        return normalized_rows

    @staticmethod
    def _normalize_scope_value(raw_value: object | None) -> str | None:
        if raw_value is None:
            return None
        normalized = str(raw_value).strip()
        return normalized or None

    async def _get_department_row(
        self,
        *,
        organization_id: str,
        department_id: str,
    ) -> dict[str, object]:
        row = await self.repository.db.fetchrow(
            """
            SELECT id, organization_id
            FROM departments
            WHERE id = $1
            LIMIT 1
            """,
            department_id,
        )
        if row is None:
            raise ValidationError("department_id is invalid")
        if str(row["organization_id"]) != str(organization_id):
            raise ValidationError("department must belong to the same organization")
        return dict(row)

    async def _get_warehouse_row(
        self,
        *,
        organization_id: str,
        warehouse_id: str,
        require_active: bool,
    ) -> dict[str, object]:
        row = await self.warehouse_repository.get_by_id_optional(warehouse_id)
        if row is None:
            raise ValidationError("warehouse_id is invalid")
        if str(row["organization_id"]) != str(organization_id):
            raise ValidationError("warehouse must belong to the same organization")
        if require_active and not bool(row.get("is_active", True)):
            raise ValidationError("warehouse is inactive")
        return row

    async def _get_default_warehouse_for_department(
        self,
        *,
        organization_id: str,
        department_id: str,
        require_active: bool,
    ) -> dict[str, object]:
        candidates = await self.warehouse_repository.list(
            filters={
                "organization_id": organization_id,
                "department_id": department_id,
            },
            order_by=("is_default DESC", "is_active DESC", "created_at", "id"),
        )
        if not candidates:
            raise ValidationError("department does not have a warehouse")

        if require_active:
            for candidate in candidates:
                if bool(candidate.get("is_active", True)) and bool(candidate.get("is_default", False)):
                    return candidate
            for candidate in candidates:
                if bool(candidate.get("is_active", True)):
                    return candidate
            raise ValidationError("department does not have an active warehouse")

        return candidates[0]

    async def _resolve_scope(
        self,
        *,
        organization_id: str,
        department_id: str | None = None,
        warehouse_id: str | None = None,
        require_warehouse: bool,
        require_active_warehouse: bool = False,
    ) -> dict[str, str | None]:
        resolved_department_id = self._normalize_scope_value(department_id)
        resolved_warehouse_id = self._normalize_scope_value(warehouse_id)

        if resolved_warehouse_id is not None:
            warehouse = await self._get_warehouse_row(
                organization_id=organization_id,
                warehouse_id=resolved_warehouse_id,
                require_active=require_active_warehouse,
            )
            warehouse_department_id = str(warehouse["department_id"])
            if resolved_department_id is not None and resolved_department_id != warehouse_department_id:
                raise ValidationError("warehouse must belong to the provided department")
            return {
                "department_id": warehouse_department_id,
                "warehouse_id": str(warehouse["id"]),
            }

        if resolved_department_id is None:
            raise ValidationError("department_id or warehouse_id is required")

        await self._get_department_row(
            organization_id=organization_id,
            department_id=resolved_department_id,
        )
        if not require_warehouse:
            return {
                "department_id": resolved_department_id,
                "warehouse_id": None,
            }

        warehouse = await self._get_default_warehouse_for_department(
            organization_id=organization_id,
            department_id=resolved_department_id,
            require_active=require_active_warehouse,
        )
        return {
            "department_id": resolved_department_id,
            "warehouse_id": str(warehouse["id"]),
        }

    async def normalize_movement_payload(
        self,
        payload: dict[str, object],
        *,
        require_active_warehouse: bool = True,
    ) -> dict[str, object]:
        next_payload = dict(payload)
        organization_id = self._normalize_scope_value(next_payload.get("organization_id"))
        if organization_id is None:
            raise ValidationError("organization_id is required")

        primary_scope = await self._resolve_scope(
            organization_id=organization_id,
            department_id=self._normalize_scope_value(next_payload.get("department_id")),
            warehouse_id=self._normalize_scope_value(next_payload.get("warehouse_id")),
            require_warehouse=True,
            require_active_warehouse=require_active_warehouse,
        )
        next_payload["organization_id"] = organization_id
        next_payload["department_id"] = primary_scope["department_id"]
        next_payload["warehouse_id"] = primary_scope["warehouse_id"]

        counterparty_department_id = self._normalize_scope_value(next_payload.get("counterparty_department_id"))
        counterparty_warehouse_id = self._normalize_scope_value(next_payload.get("counterparty_warehouse_id"))
        if counterparty_department_id is not None or counterparty_warehouse_id is not None:
            counterparty_scope = await self._resolve_scope(
                organization_id=organization_id,
                department_id=counterparty_department_id,
                warehouse_id=counterparty_warehouse_id,
                require_warehouse=True,
                require_active_warehouse=require_active_warehouse,
            )
            next_payload["counterparty_department_id"] = counterparty_scope["department_id"]
            next_payload["counterparty_warehouse_id"] = counterparty_scope["warehouse_id"]
        else:
            next_payload["counterparty_department_id"] = None
            next_payload["counterparty_warehouse_id"] = None

        return next_payload

    async def record_movement(
        self,
        movement: StockMovementDraft,
        *,
        exclude_reference_check: bool = False,
    ) -> dict[str, object]:
        normalized_scope = await self.normalize_movement_payload(
            {
                "organization_id": movement.organization_id,
                "department_id": movement.department_id,
                "warehouse_id": movement.warehouse_id,
                "counterparty_department_id": movement.counterparty_department_id,
                "counterparty_warehouse_id": movement.counterparty_warehouse_id,
            }
        )
        quantity = self._to_decimal(movement.quantity)
        if movement.movement_kind in MINUS_MOVEMENTS:
            available_balance = await self.repository.get_balance(
                organization_id=str(normalized_scope["organization_id"]),
                warehouse_id=str(normalized_scope["warehouse_id"]),
                department_id=str(normalized_scope["department_id"]),
                item_type=movement.item_type,
                item_key=movement.item_key,
                as_of=movement.occurred_on,
                exclude_reference_table=(movement.reference_table if exclude_reference_check else None),
                exclude_reference_id=(movement.reference_id if exclude_reference_check else None),
            )
            if quantity > available_balance:
                has_existing_movements = await self.repository.has_item_movements(
                    organization_id=str(normalized_scope["organization_id"]),
                    warehouse_id=str(normalized_scope["warehouse_id"]),
                    department_id=str(normalized_scope["department_id"]),
                    item_type=movement.item_type,
                    item_key=movement.item_key,
                )
                if has_existing_movements and available_balance >= 0:
                    raise ValidationError(
                        f"Insufficient stock for {movement.item_type}:{movement.item_key}. "
                        f"Available={available_balance}, requested={quantity}."
                    )

        payload: dict[str, object] = {
            "id": str(uuid4()),
            "organization_id": normalized_scope["organization_id"],
            "department_id": normalized_scope["department_id"],
            "warehouse_id": normalized_scope["warehouse_id"],
            "counterparty_department_id": normalized_scope["counterparty_department_id"],
            "counterparty_warehouse_id": normalized_scope["counterparty_warehouse_id"],
            "item_type": movement.item_type,
            "item_key": movement.item_key,
            "movement_kind": movement.movement_kind,
            "quantity": str(quantity),
            "unit": movement.unit,
            "occurred_on": movement.occurred_on,
            "reference_table": movement.reference_table,
            "reference_id": movement.reference_id,
            "note": movement.note,
        }
        return await self.repository.create(payload)

    async def replace_reference_movements(
        self,
        *,
        reference_table: str,
        reference_id: str,
        movements: list[StockMovementDraft],
    ) -> None:
        await self.repository.delete_by_reference(
            reference_table=reference_table,
            reference_id=reference_id,
        )
        for movement in movements:
            await self.record_movement(movement, exclude_reference_check=True)

    async def clear_reference_movements(
        self,
        *,
        reference_table: str,
        reference_id: str,
    ) -> int:
        return await self.repository.delete_by_reference(
            reference_table=reference_table,
            reference_id=reference_id,
        )

    async def transfer_between_departments(
        self,
        *,
        organization_id: str,
        item_type: str,
        item_key: str,
        quantity: Decimal,
        unit: str,
        occurred_on: date,
        from_department_id: str | None,
        to_department_id: str | None,
        from_warehouse_id: str | None = None,
        to_warehouse_id: str | None = None,
        note: str | None = None,
    ) -> dict[str, object]:
        normalized_item_type = str(item_type or "").strip().lower()
        normalized_item_key = str(item_key or "").strip()
        normalized_unit = normalize_stock_movement_unit(unit)
        if normalized_item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        if not normalized_item_key:
            raise ValidationError("item_key is required")

        from_scope = await self._resolve_scope(
            organization_id=organization_id,
            department_id=from_department_id,
            warehouse_id=from_warehouse_id,
            require_warehouse=True,
            require_active_warehouse=True,
        )
        to_scope = await self._resolve_scope(
            organization_id=organization_id,
            department_id=to_department_id,
            warehouse_id=to_warehouse_id,
            require_warehouse=True,
            require_active_warehouse=True,
        )
        if str(from_scope["warehouse_id"]) == str(to_scope["warehouse_id"]):
            raise ValidationError("source and destination warehouses must be different")
        if not await _inventory_item_key_exists(
            db=self.repository.db,
            organization_id=organization_id,
            item_type=normalized_item_type,
            item_key=normalized_item_key,
            department_id=str(from_scope["department_id"]),
        ):
            raise ValidationError("item_key is invalid for selected item_type")

        transfer_id = str(uuid4())
        outgoing = StockMovementDraft(
            organization_id=organization_id,
            department_id=str(from_scope["department_id"]),
            warehouse_id=str(from_scope["warehouse_id"]),
            counterparty_department_id=str(to_scope["department_id"]),
            counterparty_warehouse_id=str(to_scope["warehouse_id"]),
            item_type=normalized_item_type,
            item_key=normalized_item_key,
            movement_kind="transfer_out",
            quantity=self._to_decimal(quantity),
            unit=normalized_unit,
            occurred_on=occurred_on,
            reference_table="stock_transfer",
            reference_id=transfer_id,
            note=note,
        )
        incoming = StockMovementDraft(
            organization_id=organization_id,
            department_id=str(to_scope["department_id"]),
            warehouse_id=str(to_scope["warehouse_id"]),
            counterparty_department_id=str(from_scope["department_id"]),
            counterparty_warehouse_id=str(from_scope["warehouse_id"]),
            item_type=normalized_item_type,
            item_key=normalized_item_key,
            movement_kind="transfer_in",
            quantity=self._to_decimal(quantity),
            unit=normalized_unit,
            occurred_on=occurred_on,
            reference_table="stock_transfer",
            reference_id=transfer_id,
            note=note,
        )

        await self.record_movement(outgoing)
        await self.record_movement(incoming)

        return {
            "transfer_id": transfer_id,
            "organization_id": organization_id,
            "item_type": normalized_item_type,
            "item_key": normalized_item_key,
            "quantity": str(outgoing.quantity),
            "unit": normalized_unit,
            "occurred_on": occurred_on,
            "from_department_id": from_scope["department_id"],
            "from_warehouse_id": from_scope["warehouse_id"],
            "to_department_id": to_scope["department_id"],
            "to_warehouse_id": to_scope["warehouse_id"],
            "note": note,
        }


class StockMovementService(BaseService):
    read_schema = StockMovementReadSchema

    def __init__(self, repository: StockMovementRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                {
                    "name": "item_type",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": _build_static_reference_options(
                            ["egg", "chick", "feed", "medicine", "semi_product"]
                        ),
                    },
                },
                {
                    "name": "movement_kind",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": _build_static_reference_options(
                            [
                                "incoming",
                                "outgoing",
                                "transfer_in",
                                "transfer_out",
                                "adjustment_in",
                                "adjustment_out",
                            ]
                        ),
                    },
                },
                {
                    "name": "unit",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": _build_static_reference_options(["pcs", "kg", "ltr"]),
                    },
                },
                {
                    "name": "item_key",
                    "reference": {
                        "table": ITEM_KEY_REFERENCE_TABLE,
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": [],
                    },
                },
            ]
        )
        return fields

    async def get_reference_options(
        self,
        field_name: str,
        *,
        db,
        actor=None,
        search: str | None = None,
        values=None,
        limit: int = 25,
        extra_params=None,
    ) -> list[dict[str, str]] | None:
        if field_name != "item_key":
            return None

        normalized_item_type = str((extra_params or {}).get("item_type") or "").strip().lower()
        if normalized_item_type not in ITEM_TYPES:
            return []

        normalized_department_id = str((extra_params or {}).get("department_id") or "").strip() or None
        organization_id = str(
            (actor.organization_id if actor is not None else None)
            or (extra_params or {}).get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            return []

        normalized_values = [str(value).strip() for value in (values or []) if str(value).strip()]
        return await _fetch_inventory_item_key_options(
            db=db,
            organization_id=organization_id,
            item_type=normalized_item_type,
            department_id=normalized_department_id,
            search=search,
            values=normalized_values,
            limit=limit,
        )

    async def _before_create(
        self,
        data: dict[str, object],
        *,
        actor=None,
    ) -> dict[str, object]:
        next_data = dict(data)
        item_type = str(next_data.get("item_type") or "").strip().lower()
        movement_kind = str(next_data.get("movement_kind") or "").strip().lower()
        item_key = str(next_data.get("item_key") or "").strip()
        unit = normalize_stock_movement_unit(next_data.get("unit"))

        if item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        if movement_kind not in PLUS_MOVEMENTS.union(MINUS_MOVEMENTS):
            raise ValidationError("movement_kind is invalid")
        if not item_key:
            raise ValidationError("item_key is required")

        quantity = StockLedgerService._to_decimal(next_data.get("quantity"))
        next_data["item_type"] = item_type
        next_data["movement_kind"] = movement_kind
        next_data["item_key"] = item_key
        next_data["unit"] = unit
        next_data["quantity"] = str(quantity)
        if "occurred_on" in next_data and next_data["occurred_on"] is not None and not isinstance(next_data["occurred_on"], date):
            next_data["occurred_on"] = date.fromisoformat(str(next_data["occurred_on"]))

        organization_id = str(
            next_data.get("organization_id")
            or (actor.organization_id if actor is not None else "")
        ).strip()
        if not organization_id:
            raise ValidationError("organization_id is required")
        next_data["organization_id"] = organization_id
        ledger = StockLedgerService(
            self.repository,
            WarehouseRepository(self.repository.db),
        )
        next_data = await ledger.normalize_movement_payload(next_data)
        if not await _inventory_item_key_exists(
            db=self.repository.db,
            organization_id=organization_id,
            item_type=item_type,
            item_key=item_key,
            department_id=str(next_data["department_id"]),
        ):
            raise ValidationError("item_key is invalid for selected item_type")

        if movement_kind in MINUS_MOVEMENTS:
            as_of = next_data.get("occurred_on")
            balance = await self.repository.get_balance(
                organization_id=organization_id,
                warehouse_id=str(next_data["warehouse_id"]),
                department_id=str(next_data["department_id"]),
                item_type=item_type,
                item_key=item_key,
                as_of=(as_of if isinstance(as_of, date) else None),
            )
            has_existing = await self.repository.has_item_movements(
                organization_id=organization_id,
                warehouse_id=str(next_data["warehouse_id"]),
                department_id=str(next_data["department_id"]),
                item_type=item_type,
                item_key=item_key,
            )
            if quantity > balance and has_existing and balance >= 0:
                raise ValidationError(
                    f"Insufficient stock for {item_type}:{item_key}. "
                    f"Available={balance}, requested={quantity}."
                )

        return next_data

    async def _before_update(
        self,
        entity_id,
        data: dict[str, object],
        *,
        existing,
        actor=None,
    ) -> dict[str, object]:
        immutable_fields = {
            "organization_id",
            "department_id",
            "warehouse_id",
            "counterparty_department_id",
            "counterparty_warehouse_id",
            "item_type",
            "item_key",
            "movement_kind",
            "quantity",
            "unit",
            "occurred_on",
            "reference_table",
            "reference_id",
        }
        for field in immutable_fields:
            if field in data:
                raise ValidationError("Stock movement core fields are immutable. Create a new movement instead.")
        return data


__all__ = [
    "StockLedgerService",
    "StockMovementDraft",
    "StockMovementService",
    "PLUS_MOVEMENTS",
    "MINUS_MOVEMENTS",
    "ITEM_TYPES",
    "normalize_stock_movement_unit",
]
