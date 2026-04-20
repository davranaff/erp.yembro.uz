from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.core import WarehouseRepository
from app.repositories.inventory import (
    StockMovementRepository,
    StockReorderLevelRepository,
    StockTakeLineRepository,
    StockTakeRepository,
)
from app.schemas.inventory import (
    StockMovementReadSchema,
    StockReorderLevelReadSchema,
    StockTakeLineReadSchema,
    StockTakeReadSchema,
)
from app.services.base import BaseService


PLUS_MOVEMENTS = {"incoming", "transfer_in", "adjustment_in"}
MINUS_MOVEMENTS = {"outgoing", "transfer_out", "adjustment_out"}
ITEM_TYPES = {"egg", "chick", "feed", "feed_raw", "medicine", "semi_product"}
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
            batch_row = await db.fetchrow(
                """
                SELECT pb.batch_code, pb.finished_on, ft.name AS feed_type_name, ft.code AS feed_type_code
                FROM feed_production_batches pb
                JOIN feed_formulas ff ON ff.id = pb.formula_id
                JOIN feed_types ft ON ft.id = ff.feed_type_id
                WHERE pb.id::text = $1
                LIMIT 1
                """,
                entity_id,
            )
            if batch_row is not None:
                return {
                    "value": normalized_item_key,
                    "label": _compose_option_label(
                        "Feed product",
                        f"{batch_row['feed_type_name']} ({batch_row['feed_type_code']})",
                        batch_row["batch_code"],
                    ),
                }
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

    if normalized_item_type == "feed_raw" and normalized_item_key.startswith("feed_raw:"):
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

    if normalized_item_type == "feed_raw":
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
                            ["egg", "chick", "feed", "feed_raw", "medicine", "semi_product"]
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
            if quantity > balance:
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


STOCK_TAKE_STATUSES = ("draft", "finalized", "cancelled")


def _item_type_reference_field() -> dict[str, Any]:
    return {
        "name": "item_type",
        "reference": {
            "table": "__static__",
            "column": "value",
            "label_column": "label",
            "multiple": False,
            "options": _build_static_reference_options(sorted(ITEM_TYPES)),
        },
    }


class StockTakeService(BaseService):
    read_schema = StockTakeReadSchema

    def __init__(self, repository: StockTakeRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.append(
            {
                "name": "status",
                "reference": {
                    "table": "__static__",
                    "column": "value",
                    "label_column": "label",
                    "multiple": False,
                    "options": _build_static_reference_options(list(STOCK_TAKE_STATUSES)),
                },
            }
        )
        return fields

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        reference_no = str(next_data.get("reference_no") or "").strip()
        if not reference_no:
            raise ValidationError("reference_no is required")
        next_data["reference_no"] = reference_no

        raw_counted_on = next_data.get("counted_on")
        if raw_counted_on is None:
            next_data["counted_on"] = date.today()
        elif isinstance(raw_counted_on, str):
            next_data["counted_on"] = date.fromisoformat(raw_counted_on)

        status_value = str(next_data.get("status") or "draft").strip().lower() or "draft"
        if status_value not in STOCK_TAKE_STATUSES:
            raise ValidationError("status is invalid")
        next_data["status"] = status_value
        next_data.pop("finalized_at", None)
        next_data.pop("finalized_by_employee_id", None)

        organization_id = str(
            next_data.get("organization_id")
            or (actor.organization_id if actor is not None else "")
        ).strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        ledger = StockLedgerService(
            StockMovementRepository(self.repository.db),
            WarehouseRepository(self.repository.db),
        )
        scope = await ledger._resolve_scope(
            organization_id=organization_id,
            department_id=str(next_data.get("department_id") or "").strip() or None,
            warehouse_id=str(next_data.get("warehouse_id") or "").strip() or None,
            require_warehouse=True,
            require_active_warehouse=True,
        )
        next_data["organization_id"] = organization_id
        next_data["department_id"] = scope["department_id"]
        next_data["warehouse_id"] = scope["warehouse_id"]
        return next_data

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing,
        actor=None,
    ) -> dict[str, Any]:
        if str(existing.get("status")) == "finalized":
            raise ValidationError("Finalized stock takes cannot be edited")

        next_data = dict(data)
        if "status" in next_data:
            requested_status = str(next_data.get("status") or "").strip().lower()
            if requested_status not in STOCK_TAKE_STATUSES:
                raise ValidationError("status is invalid")
            if requested_status == "finalized":
                raise ValidationError("Use POST /stock-takes/{id}/finalize to finalize")
            next_data["status"] = requested_status
        return next_data

    async def finalize(
        self,
        stock_take_id: str,
        *,
        actor=None,
    ) -> dict[str, Any]:
        db = self.repository.db
        async with db.transaction():
            stock_take = await self.repository.get_by_id(stock_take_id)
            self._ensure_actor_can_access_entity(stock_take, actor=actor)
            status_value = str(stock_take.get("status") or "").strip().lower()
            if status_value == "finalized":
                raise ValidationError("Stock take is already finalized")
            if status_value == "cancelled":
                raise ValidationError("Cancelled stock takes cannot be finalized")

            line_repo = StockTakeLineRepository(db)
            lines = await line_repo.list_by_stock_take(str(stock_take["id"]))

            ledger = StockLedgerService(
                StockMovementRepository(db),
                WarehouseRepository(db),
            )

            counted_on = stock_take["counted_on"]
            if isinstance(counted_on, str):
                counted_on = date.fromisoformat(counted_on)

            for line in lines:
                item_type = str(line["item_type"]).strip().lower()
                item_key = str(line["item_key"]).strip()
                if item_type not in ITEM_TYPES or not item_key:
                    continue

                current_balance = await StockMovementRepository(db).get_balance(
                    organization_id=str(stock_take["organization_id"]),
                    warehouse_id=str(stock_take["warehouse_id"]),
                    department_id=str(stock_take["department_id"]),
                    item_type=item_type,
                    item_key=item_key,
                    as_of=counted_on,
                )

                counted_raw = line.get("counted_quantity") or 0
                counted_quantity = (
                    counted_raw if isinstance(counted_raw, Decimal) else Decimal(str(counted_raw))
                ).quantize(Decimal("0.001"))

                diff = counted_quantity - current_balance
                if diff == 0:
                    continue

                movement_kind = "adjustment_in" if diff > 0 else "adjustment_out"
                draft = StockMovementDraft(
                    organization_id=str(stock_take["organization_id"]),
                    department_id=str(stock_take["department_id"]),
                    warehouse_id=str(stock_take["warehouse_id"]),
                    item_type=item_type,
                    item_key=item_key,
                    movement_kind=movement_kind,
                    quantity=abs(diff),
                    unit=normalize_stock_movement_unit(line.get("unit")),
                    occurred_on=counted_on,
                    reference_table="stock_take",
                    reference_id=str(stock_take["id"]),
                    note=f"Stock take {stock_take.get('reference_no')}",
                )
                await ledger.record_movement(draft)

            finalize_payload: dict[str, Any] = {
                "status": "finalized",
                "finalized_at": datetime.now(timezone.utc),
                "finalized_by_employee_id": (
                    actor.employee_id if actor is not None else None
                ),
            }
            updated = await self.repository.update_by_id(stock_take_id, finalize_payload)
            await self._record_audit_event(
                action="update",
                entity_id=stock_take_id,
                before_data=stock_take,
                after_data=updated,
                actor=actor,
                context_data={"operation": "finalize_stock_take"},
            )
        return updated


class StockTakeLineService(BaseService):
    read_schema = StockTakeLineReadSchema

    def __init__(self, repository: StockTakeLineRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                _item_type_reference_field(),
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
        organization_id = str(
            (actor.organization_id if actor is not None else None)
            or (extra_params or {}).get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            return []
        normalized_department_id = str((extra_params or {}).get("department_id") or "").strip() or None
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
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        stock_take_id = str(next_data.get("stock_take_id") or "").strip()
        if not stock_take_id:
            raise ValidationError("stock_take_id is required")

        take_repo = StockTakeRepository(self.repository.db)
        try:
            stock_take = await take_repo.get_by_id(stock_take_id)
        except NotFoundError as exc:
            raise ValidationError("stock_take_id is invalid") from exc
        if actor is not None and not self._actor_bypasses_organization_scope(actor):
            if str(stock_take["organization_id"]) != actor.organization_id:
                raise ValidationError("stock_take belongs to a different organization")
        if str(stock_take.get("status")) == "finalized":
            raise ValidationError("Finalized stock takes cannot be edited")

        item_type = str(next_data.get("item_type") or "").strip().lower()
        if item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        next_data["item_type"] = item_type

        item_key = str(next_data.get("item_key") or "").strip()
        if not item_key:
            raise ValidationError("item_key is required")
        next_data["item_key"] = item_key

        next_data["unit"] = normalize_stock_movement_unit(next_data.get("unit"))
        for field in ("expected_quantity", "counted_quantity"):
            raw_value = next_data.get(field)
            if raw_value is None or str(raw_value).strip() == "":
                next_data[field] = Decimal("0")
                continue
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError(f"{field} has an invalid value") from exc
            if value < 0:
                raise ValidationError(f"{field} must be non-negative")
            next_data[field] = value.quantize(Decimal("0.001"))
        return next_data

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing,
        actor=None,
    ) -> dict[str, Any]:
        take_repo = StockTakeRepository(self.repository.db)
        stock_take = await take_repo.get_by_id(str(existing["stock_take_id"]))
        if str(stock_take.get("status")) == "finalized":
            raise ValidationError("Finalized stock takes cannot be edited")

        next_data = dict(data)
        if "stock_take_id" in next_data and str(next_data["stock_take_id"]) != str(existing["stock_take_id"]):
            raise ValidationError("stock_take_id cannot be changed")
        if "item_type" in next_data:
            item_type = str(next_data.get("item_type") or "").strip().lower()
            if item_type not in ITEM_TYPES:
                raise ValidationError("item_type is invalid")
            next_data["item_type"] = item_type
        if "item_key" in next_data:
            item_key = str(next_data.get("item_key") or "").strip()
            if not item_key:
                raise ValidationError("item_key is required")
            next_data["item_key"] = item_key
        if "unit" in next_data:
            next_data["unit"] = normalize_stock_movement_unit(next_data.get("unit"))
        for field in ("expected_quantity", "counted_quantity"):
            if field not in next_data:
                continue
            raw_value = next_data[field]
            if raw_value is None:
                continue
            try:
                value = Decimal(str(raw_value))
            except (InvalidOperation, ValueError) as exc:
                raise ValidationError(f"{field} has an invalid value") from exc
            if value < 0:
                raise ValidationError(f"{field} must be non-negative")
            next_data[field] = value.quantize(Decimal("0.001"))
        return next_data


class StockReorderLevelService(BaseService):
    read_schema = StockReorderLevelReadSchema

    def __init__(self, repository: StockReorderLevelRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                _item_type_reference_field(),
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
        organization_id = str(
            (actor.organization_id if actor is not None else None)
            or (extra_params or {}).get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            return []
        normalized_department_id = str((extra_params or {}).get("department_id") or "").strip() or None
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
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        organization_id = str(
            next_data.get("organization_id")
            or (actor.organization_id if actor is not None else "")
        ).strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        ledger = StockLedgerService(
            StockMovementRepository(self.repository.db),
            WarehouseRepository(self.repository.db),
        )
        scope = await ledger._resolve_scope(
            organization_id=organization_id,
            department_id=str(next_data.get("department_id") or "").strip() or None,
            warehouse_id=str(next_data.get("warehouse_id") or "").strip() or None,
            require_warehouse=True,
            require_active_warehouse=True,
        )
        next_data["organization_id"] = organization_id
        next_data["department_id"] = scope["department_id"]
        next_data["warehouse_id"] = scope["warehouse_id"]

        item_type = str(next_data.get("item_type") or "").strip().lower()
        if item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        next_data["item_type"] = item_type

        item_key = str(next_data.get("item_key") or "").strip()
        if not item_key:
            raise ValidationError("item_key is required")
        next_data["item_key"] = item_key

        next_data["unit"] = normalize_stock_movement_unit(next_data.get("unit"))

        min_quantity = self._normalize_non_negative(next_data.get("min_quantity") or 0, "min_quantity")
        next_data["min_quantity"] = min_quantity

        max_raw = next_data.get("max_quantity")
        if max_raw is None or str(max_raw).strip() == "":
            next_data["max_quantity"] = None
        else:
            max_quantity = self._normalize_non_negative(max_raw, "max_quantity")
            if max_quantity < min_quantity:
                raise ValidationError("max_quantity must be >= min_quantity")
            next_data["max_quantity"] = max_quantity

        reorder_raw = next_data.get("reorder_quantity")
        if reorder_raw is None or str(reorder_raw).strip() == "":
            next_data["reorder_quantity"] = None
        else:
            next_data["reorder_quantity"] = self._normalize_non_negative(reorder_raw, "reorder_quantity")

        return next_data

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        if "item_type" in next_data:
            item_type = str(next_data.get("item_type") or "").strip().lower()
            if item_type not in ITEM_TYPES:
                raise ValidationError("item_type is invalid")
            next_data["item_type"] = item_type
        if "item_key" in next_data:
            item_key = str(next_data.get("item_key") or "").strip()
            if not item_key:
                raise ValidationError("item_key is required")
            next_data["item_key"] = item_key
        if "unit" in next_data:
            next_data["unit"] = normalize_stock_movement_unit(next_data.get("unit"))
        for field in ("min_quantity", "max_quantity", "reorder_quantity"):
            if field not in next_data:
                continue
            raw = next_data[field]
            if raw is None or str(raw).strip() == "":
                if field == "min_quantity":
                    raise ValidationError("min_quantity is required")
                next_data[field] = None
                continue
            next_data[field] = self._normalize_non_negative(raw, field)

        resolved_min = (
            next_data["min_quantity"] if "min_quantity" in next_data else existing.get("min_quantity")
        )
        resolved_max = next_data.get("max_quantity", existing.get("max_quantity"))
        if resolved_min is not None and resolved_max is not None:
            if Decimal(str(resolved_max)) < Decimal(str(resolved_min)):
                raise ValidationError("max_quantity must be >= min_quantity")
        return next_data

    @staticmethod
    def _normalize_non_negative(raw_value: Any, field: str) -> Decimal:
        try:
            value = Decimal(str(raw_value))
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError(f"{field} has an invalid value") from exc
        if value < 0:
            raise ValidationError(f"{field} must be non-negative")
        return value.quantize(Decimal("0.001"))

    async def list_low_stock(
        self,
        *,
        organization_id: str,
        department_id: str | None = None,
        warehouse_id: str | None = None,
        as_of: date | None = None,
    ) -> list[dict[str, Any]]:
        params: list[Any] = [organization_id]
        cursor = 2
        scope_where: list[str] = []
        if warehouse_id:
            scope_where.append(f"l.warehouse_id = ${cursor}")
            params.append(warehouse_id)
            cursor += 1
        elif department_id:
            scope_where.append(f"l.department_id = ${cursor}")
            params.append(department_id)
            cursor += 1

        as_of_cursor: int | None = None
        if as_of is not None:
            as_of_cursor = cursor
            params.append(as_of)
            cursor += 1

        as_of_clause = (
            f" AND sm.occurred_on <= ${as_of_cursor}" if as_of_cursor is not None else ""
        )
        scope_clause = (" AND " + " AND ".join(scope_where)) if scope_where else ""

        sql = f"""
        SELECT
            l.id,
            l.organization_id,
            l.department_id,
            l.warehouse_id,
            l.item_type,
            l.item_key,
            l.unit,
            l.min_quantity,
            l.max_quantity,
            l.reorder_quantity,
            COALESCE(balances.balance, 0) AS current_balance
        FROM stock_reorder_levels AS l
        LEFT JOIN LATERAL (
            SELECT COALESCE(
                SUM(
                    CASE
                        WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in')
                        THEN sm.quantity
                        ELSE -sm.quantity
                    END
                ), 0
            ) AS balance
            FROM stock_movements AS sm
            WHERE sm.organization_id = l.organization_id
              AND sm.warehouse_id = l.warehouse_id
              AND sm.department_id = l.department_id
              AND sm.item_type = l.item_type
              AND sm.item_key = l.item_key
              {as_of_clause}
        ) AS balances ON TRUE
        WHERE l.organization_id = $1
          AND l.is_active = TRUE
          {scope_clause}
          AND COALESCE(balances.balance, 0) < l.min_quantity
        ORDER BY l.item_type, l.item_key
        """

        rows = await self.repository.db.fetch(sql, *params)
        results: list[dict[str, Any]] = []
        for row in rows:
            min_quantity = Decimal(str(row["min_quantity"] or 0))
            balance = Decimal(str(row["current_balance"] or 0))
            results.append(
                {
                    "id": str(row["id"]),
                    "organization_id": str(row["organization_id"]),
                    "department_id": str(row["department_id"]),
                    "warehouse_id": str(row["warehouse_id"]),
                    "item_type": row["item_type"],
                    "item_key": row["item_key"],
                    "unit": row["unit"],
                    "min_quantity": str(min_quantity),
                    "max_quantity": (
                        str(row["max_quantity"]) if row["max_quantity"] is not None else None
                    ),
                    "reorder_quantity": (
                        str(row["reorder_quantity"])
                        if row["reorder_quantity"] is not None
                        else None
                    ),
                    "current_balance": str(balance.quantize(Decimal("0.001"))),
                    "shortage": str((min_quantity - balance).quantize(Decimal("0.001"))),
                }
            )
        return results


__all__ = [
    "StockLedgerService",
    "StockMovementDraft",
    "StockMovementService",
    "StockTakeService",
    "StockTakeLineService",
    "StockReorderLevelService",
    "PLUS_MOVEMENTS",
    "MINUS_MOVEMENTS",
    "ITEM_TYPES",
    "STOCK_TAKE_STATUSES",
    "normalize_stock_movement_unit",
]
