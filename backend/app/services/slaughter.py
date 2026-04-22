from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from app.core.exceptions import AccessDeniedError, ValidationError
from app.repositories.core import ClientDebtRepository, ClientRepository, PoultryTypeRepository, WarehouseRepository
from app.repositories.factory import FactoryShipmentRepository
from app.repositories.finance import SupplierDebtRepository
from app.repositories.inventory import StockMovementRepository
from app.repositories.hr import EmployeeRepository
from app.repositories.slaughter import (
    SlaughterArrivalRepository,
    SlaughterProcessingRepository,
    SlaughterQualityCheckRepository,
    SlaughterSemiProductRepository,
    SlaughterSemiProductShipmentRepository,
)
from app.schemas.slaughter import (
    SlaughterArrivalReadSchema,
    SlaughterProcessingReadSchema,
    SlaughterQualityCheckReadSchema,
    SlaughterSemiProductReadSchema,
    SlaughterSemiProductShipmentReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft


from app.services.units import resolve_measurement_unit_id as _resolve_measurement_unit_id

SLAUGHTER_SOURCE_TYPES = ("factory", "external")
SEMI_PRODUCT_QUALITIES = ("first", "second", "mixed", "byproduct")
SEMI_PRODUCT_CODE_PATTERN = re.compile(r"^SP-(\d{8})-(\d{3,})$")
QUALITY_CHECK_STATUSES = ("pending", "passed", "failed")

AUTO_SLAUGHTER_SHIPMENT_AR_MARKER_PREFIX = "[auto-slaughter-shipment-ar:"
AUTO_SLAUGHTER_ARRIVAL_AP_MARKER_PREFIX = "[auto-slaughter-arrival-ap:"


def _build_auto_ar_marker(shipment_id: str) -> str:
    return f"{AUTO_SLAUGHTER_SHIPMENT_AR_MARKER_PREFIX}{shipment_id}]"


def _build_auto_ap_marker(arrival_id: str) -> str:
    return f"{AUTO_SLAUGHTER_ARRIVAL_AP_MARKER_PREFIX}{arrival_id}]"


def _compose_auto_debt_note(marker: str, source_note: Any) -> str:
    note_text = str(source_note).strip() if source_note is not None else ""
    if not note_text:
        return marker
    if marker in note_text:
        return note_text
    return f"{note_text}\n{marker}"


def _resolve_auto_debt_status(amount_total: Decimal, amount_paid: Decimal) -> str:
    if amount_paid <= Decimal("0"):
        return "open"
    if amount_paid >= amount_total:
        return "closed"
    return "partially_paid"


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0)).quantize(Decimal("0.001"))


def _semi_product_key(semi_product_id: str) -> str:
    return f"semi_product:{semi_product_id}"


def _optional_decimal(raw_value: object, *, quantize: str = "0.001") -> Decimal | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, str) and not raw_value.strip():
        return None
    try:
        return Decimal(str(raw_value)).quantize(Decimal(quantize))
    except Exception as exc:
        raise ValidationError("Invalid decimal value") from exc


def _required_decimal(raw_value: object, field: str, *, quantize: str = "0.001") -> Decimal:
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        raise ValidationError(f"{field} is required")
    try:
        value = Decimal(str(raw_value)).quantize(Decimal(quantize))
    except Exception as exc:
        raise ValidationError(f"{field} has an invalid value") from exc
    if value <= 0:
        raise ValidationError(f"{field} must be positive")
    return value


def _normalize_currency(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip().upper()
    return text or None


class SlaughterArrivalService(CreatedByActorMixin, BaseService):
    """Incoming batch of live birds to the slaughterhouse."""

    read_schema = SlaughterArrivalReadSchema

    def __init__(self, repository: SlaughterArrivalRepository) -> None:
        super().__init__(repository=repository)

    async def _resolve_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update({k: v for k, v in data.items() if k in data})

        out: dict[str, Any] = dict(data)

        if "arrival_total_weight_kg" in out:
            out["arrival_total_weight_kg"] = _optional_decimal(out.get("arrival_total_weight_kg"))
        if "arrival_unit_price" in out:
            out["arrival_unit_price"] = _optional_decimal(out.get("arrival_unit_price"), quantize="0.01")

        birds_received = merged.get("birds_received")
        if birds_received is None:
            raise ValidationError("birds_received is required")
        try:
            birds_received_int = int(birds_received)
        except (TypeError, ValueError) as exc:
            raise ValidationError("birds_received must be an integer") from exc
        if birds_received_int < 0:
            raise ValidationError("birds_received must be non-negative")

        return out

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        """Incoming `chick` at slaughter warehouse when live birds arrive."""
        birds_received = int(entity.get("birds_received") or 0)
        movements: list[StockMovementDraft] = []
        if birds_received > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_slaughter_arrival_chick_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=Decimal(birds_received),
                    unit="dona",
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="slaughter_arrivals",
                    reference_id=str(entity["id"]),
                    note=None,
                )
            )
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="slaughter_arrivals",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="slaughter_arrivals",
            reference_id=str(deleted_entity["id"]),
        )


def _slaughter_arrival_chick_key(arrival_id: str) -> str:
    """Item key that ties arrival (incoming) and processing (outgoing) chick flows."""
    return f"chick_slaughter:{arrival_id}"


class SlaughterProcessingService(CreatedByActorMixin, BaseService):
    """Slaughter processing: takes an arrival batch and records yield per quality tier."""

    read_schema = SlaughterProcessingReadSchema
    created_by_field = "processed_by"

    def __init__(self, repository: SlaughterProcessingRepository) -> None:
        super().__init__(repository=repository)

    async def _resolve_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        arrival_id_raw = merged.get("arrival_id")
        if not arrival_id_raw:
            raise ValidationError("arrival_id is required")
        arrival_id = str(arrival_id_raw)

        arrival_repo = SlaughterArrivalRepository(self.repository.db)
        arrival = await arrival_repo.get_by_id_optional(arrival_id)
        if arrival is None:
            raise ValidationError("arrival_id not found")

        organization_id = str(merged.get("organization_id") or arrival.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(arrival.get("organization_id")) != organization_id:
            raise AccessDeniedError("arrival belongs to another organization")

        arrival_dept = arrival.get("department_id")
        if arrival_dept is None:
            raise ValidationError("department_id is required")
        out["department_id"] = str(arrival_dept)
        merged["department_id"] = str(arrival_dept)
        out["arrival_id"] = arrival_id

        birds_received = int(arrival.get("birds_received") or 0)

        birds_processed = merged.get("birds_processed") or 0
        try:
            birds_processed_int = int(birds_processed)
        except (TypeError, ValueError) as exc:
            raise ValidationError("birds_processed must be an integer") from exc
        if birds_processed_int < 0:
            raise ValidationError("birds_processed must be non-negative")
        if birds_processed_int > birds_received:
            raise ValidationError("birds_processed cannot exceed arrival.birds_received")

        return out

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        if "arrival_id" in data and str(data["arrival_id"]) != str(existing.get("arrival_id")):
            raise ValidationError("arrival_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        """Outgoing `chick` from slaughter warehouse: live birds consumed by processing.

        Uses the same item_key as SlaughterArrivalService._sync_stock so that
        balance per arrival = birds_received − sum(birds_processed).
        """
        birds_processed = int(entity.get("birds_processed") or 0)
        movements: list[StockMovementDraft] = []
        if birds_processed > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_slaughter_arrival_chick_key(str(entity["arrival_id"])),
                    movement_kind="outgoing",
                    quantity=Decimal(birds_processed),
                    unit="dona",
                    occurred_on=_as_date(entity["processed_on"]),
                    reference_table="slaughter_processings",
                    reference_id=str(entity["id"]),
                    note=str(entity.get("note") or "") or None,
                )
            )
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="slaughter_processings",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="slaughter_processings",
            reference_id=str(deleted_entity["id"]),
        )


class SlaughterSemiProductService(BaseService):
    read_schema = SlaughterSemiProductReadSchema

    def __init__(self, repository: SlaughterSemiProductRepository) -> None:
        super().__init__(repository=repository)

    async def _resolve_semi_product_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        processing_id_raw = merged.get("processing_id")
        if not processing_id_raw:
            raise ValidationError("processing_id is required")
        processing_id = str(processing_id_raw)

        processing_repo = SlaughterProcessingRepository(self.repository.db)
        processing = await processing_repo.get_by_id_optional(processing_id)
        if processing is None:
            raise ValidationError("processing_id not found")

        organization_id = str(merged.get("organization_id") or processing.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(processing.get("organization_id")) != organization_id:
            raise AccessDeniedError("processing belongs to another organization")

        processing_dept = processing.get("department_id")
        if processing_dept is None:
            raise ValidationError("department_id is required")
        out["department_id"] = str(processing_dept)
        merged["department_id"] = str(processing_dept)

        out["processing_id"] = processing_id

        poultry_type_id = merged.get("poultry_type_id")
        if poultry_type_id:
            poultry_repo = PoultryTypeRepository(self.repository.db)
            poultry = await poultry_repo.get_by_id_optional(str(poultry_type_id))
            if poultry is None:
                raise ValidationError("poultry_type_id not found")
            if str(poultry.get("organization_id")) != organization_id:
                raise AccessDeniedError("poultry type belongs to another organization")
            out["poultry_type_id"] = str(poultry_type_id)
        elif "poultry_type_id" in data:
            out["poultry_type_id"] = None

        warehouse_id = merged.get("warehouse_id")
        if warehouse_id:
            warehouse_repo = WarehouseRepository(self.repository.db)
            warehouse = await warehouse_repo.get_by_id_optional(str(warehouse_id))
            if warehouse is None:
                raise ValidationError("warehouse_id not found")
            if str(warehouse.get("organization_id")) != organization_id:
                raise AccessDeniedError("warehouse belongs to another organization")
            warehouse_dept = warehouse.get("department_id")
            if warehouse_dept is not None and str(warehouse_dept) != str(
                out.get("department_id") or merged.get("department_id")
            ):
                raise ValidationError("warehouse must belong to the same department")
            out["warehouse_id"] = str(warehouse_id)
        elif "warehouse_id" in data:
            out["warehouse_id"] = None

        quality_raw = merged.get("quality")
        if quality_raw is None or str(quality_raw).strip() == "":
            quality = "first"
        else:
            quality = str(quality_raw).strip().lower()
        if quality not in SEMI_PRODUCT_QUALITIES:
            raise ValidationError(
                f"quality must be one of: {', '.join(SEMI_PRODUCT_QUALITIES)}",
            )
        out["quality"] = quality

        if existing is None or "produced_on" in data:
            produced_on_raw = merged.get("produced_on")
            if not produced_on_raw:
                raise ValidationError("produced_on is required")

        if existing is None or "quantity" in data:
            out["quantity"] = _required_decimal(merged.get("quantity"), "quantity")

        unit_raw = merged.get("unit")
        if unit_raw is not None:
            unit = str(unit_raw).strip().lower()
            if unit:
                out["unit"] = unit
            elif "unit" in data:
                out["unit"] = "kg"
        elif existing is None:
            out["unit"] = "kg"

        part_name = merged.get("part_name")
        if part_name is not None and isinstance(part_name, str):
            trimmed = part_name.strip()
            out["part_name"] = trimmed or None

        if existing is None:
            code_raw = data.get("code")
            if code_raw is None or str(code_raw).strip() == "":
                out["code"] = await self._generate_code(
                    organization_id=organization_id,
                    processing_id=processing_id,
                    produced_on=merged.get("produced_on"),
                )
            else:
                out["code"] = str(code_raw).strip()
        elif "code" in data:
            code_raw = data.get("code")
            if code_raw is None or str(code_raw).strip() == "":
                raise ValidationError("code cannot be empty")
            out["code"] = str(code_raw).strip()

        return out

    async def _generate_code(
        self,
        *,
        organization_id: str,
        processing_id: str,
        produced_on: Any,
    ) -> str:
        try:
            produced_date = _as_date(produced_on) if produced_on else date.today()
        except Exception:
            produced_date = date.today()
        date_token = produced_date.strftime("%Y%m%d")

        existing_codes = await self.repository.pluck(
            column="code",
            filters={
                "organization_id": organization_id,
                "processing_id": processing_id,
            },
        )

        max_seq = 0
        for raw in existing_codes or []:
            if raw is None:
                continue
            match = SEMI_PRODUCT_CODE_PATTERN.match(str(raw))
            if not match:
                continue
            if match.group(1) != date_token:
                continue
            try:
                seq = int(match.group(2))
            except ValueError:
                continue
            if seq > max_seq:
                max_seq = seq

        next_seq = max_seq + 1
        return f"SP-{date_token}-{next_seq:03d}"

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_semi_product_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        if "processing_id" in data and str(data["processing_id"]) != str(existing.get("processing_id")):
            raise ValidationError("processing_id cannot be changed")
        return await self._resolve_semi_product_fields(data, existing=existing)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="semi_product",
                    item_key=_semi_product_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["produced_on"]),
                    reference_table="slaughter_semi_products",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("code")) if entity.get("code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="slaughter_semi_products",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="slaughter_semi_products",
            reference_id=str(deleted_entity["id"]),
        )


class SlaughterSemiProductShipmentService(CreatedByActorMixin, BaseService):
    read_schema = SlaughterSemiProductShipmentReadSchema

    def __init__(self, repository: SlaughterSemiProductShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _ensure_quality_passed(self, semi_product_id: str) -> None:
        qc_repo = SlaughterQualityCheckRepository(self.repository.db)
        latest = await qc_repo.get_optional_by(
            filters={"semi_product_id": semi_product_id},
            order_by=("checked_on desc", "created_at desc"),
        )
        if latest is None:
            raise ValidationError(
                "Shipment blocked: semi product has no quality check yet",
            )
        status = str(latest.get("status") or "").strip().lower()
        if status != "passed":
            raise ValidationError(
                f"Shipment blocked: latest quality check status is '{status}' (must be 'passed')",
            )

    async def _resolve_shipment_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        semi_product_id_raw = merged.get("semi_product_id")
        if not semi_product_id_raw:
            raise ValidationError("semi_product_id is required")
        semi_product_id = str(semi_product_id_raw)

        semi_product_repo = SlaughterSemiProductRepository(self.repository.db)
        semi_product = await semi_product_repo.get_by_id_optional(semi_product_id)
        if semi_product is None:
            raise ValidationError("semi_product_id not found")

        organization_id = str(merged.get("organization_id") or semi_product.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(semi_product.get("organization_id")) != organization_id:
            raise AccessDeniedError("semi product belongs to another organization")

        sp_dept = semi_product.get("department_id")
        if sp_dept is None:
            raise ValidationError("department_id is required")
        out["department_id"] = str(sp_dept)
        merged["department_id"] = str(sp_dept)

        out["semi_product_id"] = semi_product_id

        await self._ensure_quality_passed(semi_product_id)

        client_id_raw = merged.get("client_id")
        if not client_id_raw:
            raise ValidationError("client_id is required")
        client_repo = ClientRepository(self.repository.db)
        client = await client_repo.get_by_id_optional(str(client_id_raw))
        if client is None:
            raise ValidationError("client_id not found")
        if str(client.get("organization_id")) != organization_id:
            raise AccessDeniedError("client belongs to another organization")
        out["client_id"] = str(client_id_raw)

        warehouse_id = merged.get("warehouse_id")
        if warehouse_id:
            warehouse_repo = WarehouseRepository(self.repository.db)
            warehouse = await warehouse_repo.get_by_id_optional(str(warehouse_id))
            if warehouse is None:
                raise ValidationError("warehouse_id not found")
            if str(warehouse.get("organization_id")) != organization_id:
                raise AccessDeniedError("warehouse belongs to another organization")
            warehouse_dept = warehouse.get("department_id")
            if warehouse_dept is not None and str(warehouse_dept) != str(
                out.get("department_id") or merged.get("department_id")
            ):
                raise ValidationError("warehouse must belong to the same department")
            out["warehouse_id"] = str(warehouse_id)
        elif "warehouse_id" in data:
            out["warehouse_id"] = None

        if existing is None or "shipped_on" in data:
            if not merged.get("shipped_on"):
                raise ValidationError("shipped_on is required")

        if existing is None or "quantity" in data:
            out["quantity"] = _required_decimal(merged.get("quantity"), "quantity")

        if existing is None or "unit_price" in data:
            out["unit_price"] = _optional_decimal(merged.get("unit_price"), quantize="0.01")

        unit_raw = merged.get("unit")
        if unit_raw is not None:
            unit = str(unit_raw).strip().lower()
            if unit:
                out["unit"] = unit
            elif "unit" in data:
                out["unit"] = "kg"
        elif existing is None:
            out["unit"] = "kg"

        invoice_no = merged.get("invoice_no")
        if invoice_no is not None and isinstance(invoice_no, str):
            trimmed = invoice_no.strip()
            out["invoice_no"] = trimmed or None

        return out

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_shipment_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        if "semi_product_id" in data and str(data["semi_product_id"]) != str(existing.get("semi_product_id")):
            raise ValidationError("semi_product_id cannot be changed")
        return await self._resolve_shipment_fields(data, existing=existing)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="semi_product",
                    item_key=_semi_product_key(str(entity["semi_product_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="slaughter_semi_product_shipments",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="slaughter_semi_product_shipments",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _find_auto_ar_debt(self, shipment_id: str) -> dict[str, Any] | None:
        marker = _build_auto_ar_marker(shipment_id)
        row = await self.repository.db.fetchrow(
            """
            SELECT *
            FROM client_debts
            WHERE note LIKE $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            f"%{marker}%",
        )
        return dict(row) if row is not None else None

    async def _sync_auto_ar(self, entity: Mapping[str, Any]) -> None:
        shipment_id = str(entity["id"])
        unit_price = entity.get("unit_price")
        quantity = _as_decimal(entity.get("quantity"))
        debt_repo = ClientDebtRepository(self.repository.db)
        existing_debt = await self._find_auto_ar_debt(shipment_id)

        if (
            not entity.get("client_id")
            or unit_price is None
            or Decimal(str(unit_price or 0)) <= 0
            or quantity <= 0
        ):
            if existing_debt is not None:
                await debt_repo.delete_by_id(str(existing_debt["id"]))
            return

        unit_price_decimal = Decimal(str(unit_price)).quantize(Decimal("0.01"))
        amount_total = (unit_price_decimal * quantity).quantize(Decimal("0.01"))
        amount_paid = Decimal(str((existing_debt or {}).get("amount_paid") or 0)).quantize(Decimal("0.01"))
        if amount_paid > amount_total:
            raise ValidationError(
                "Cannot reduce shipment total below already recorded debt payments",
            )

        marker = _build_auto_ar_marker(shipment_id)
        note = _compose_auto_debt_note(
            marker,
            (existing_debt or {}).get("note") if existing_debt else None,
        )
        status = _resolve_auto_debt_status(amount_total, amount_paid)
        issued_on = _as_date(entity["shipped_on"])

        unit_code = str(entity.get("unit") or "kg")
        measurement_unit_id = await _resolve_measurement_unit_id(
            self.repository.db, str(entity["organization_id"]), unit_code,
        )
        payload: dict[str, Any] = {
            "organization_id": str(entity["organization_id"]),
            "department_id": str(entity["department_id"]),
            "client_id": str(entity["client_id"]),
            "item_type": "semi_product",
            "item_key": f"slaughter_shipment:{shipment_id}",
            "quantity": str(quantity),
            "unit": unit_code,
            "measurement_unit_id": measurement_unit_id,
            "amount_total": str(amount_total),
            "amount_paid": str(amount_paid),
            "currency_id": str(entity["currency_id"]),
            "issued_on": issued_on,
            "status": status,
            "note": note,
            "is_active": True,
        }

        if existing_debt is None:
            await debt_repo.create({"id": str(uuid4()), **payload})
        else:
            await debt_repo.update_by_id(str(existing_debt["id"]), payload)

    async def _delete_auto_ar(self, shipment_id: str) -> None:
        existing_debt = await self._find_auto_ar_debt(shipment_id)
        if existing_debt is None:
            return
        await ClientDebtRepository(self.repository.db).delete_by_id(str(existing_debt["id"]))

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)
        await self._sync_auto_ar(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)
        await self._sync_auto_ar(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="slaughter_semi_product_shipments",
            reference_id=str(deleted_entity["id"]),
        )
        await self._delete_auto_ar(str(deleted_entity["id"]))


class SlaughterQualityCheckService(BaseService):
    read_schema = SlaughterQualityCheckReadSchema

    def __init__(self, repository: SlaughterQualityCheckRepository) -> None:
        super().__init__(repository=repository)

    async def _resolve_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        semi_product_id_raw = merged.get("semi_product_id")
        if not semi_product_id_raw:
            raise ValidationError("semi_product_id is required")
        semi_product_id = str(semi_product_id_raw)

        semi_product_repo = SlaughterSemiProductRepository(self.repository.db)
        semi_product = await semi_product_repo.get_by_id_optional(semi_product_id)
        if semi_product is None:
            raise ValidationError("semi_product_id not found")

        organization_id = str(merged.get("organization_id") or semi_product.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(semi_product.get("organization_id")) != organization_id:
            raise AccessDeniedError("semi product belongs to another organization")

        sp_dept = semi_product.get("department_id")
        if sp_dept is None:
            raise ValidationError("department_id is required")
        out["department_id"] = str(sp_dept)
        merged["department_id"] = str(sp_dept)

        out["semi_product_id"] = semi_product_id

        status_raw = merged.get("status")
        status = (str(status_raw).strip().lower() if status_raw else "pending") or "pending"
        if status not in QUALITY_CHECK_STATUSES:
            raise ValidationError(
                f"status must be one of: {', '.join(QUALITY_CHECK_STATUSES)}",
            )
        out["status"] = status

        grade_raw = merged.get("grade")
        if grade_raw:
            grade = str(grade_raw).strip().lower()
            if grade not in SEMI_PRODUCT_QUALITIES:
                raise ValidationError(
                    f"grade must be one of: {', '.join(SEMI_PRODUCT_QUALITIES)}",
                )
            out["grade"] = grade
        elif "grade" in data:
            out["grade"] = None

        inspector_id = merged.get("inspector_id")
        if inspector_id:
            employee_repo = EmployeeRepository(self.repository.db)
            inspector = await employee_repo.get_by_id_optional(str(inspector_id))
            if inspector is None:
                raise ValidationError("inspector_id not found")
            if str(inspector.get("organization_id")) != organization_id:
                raise AccessDeniedError("inspector belongs to another organization")
            out["inspector_id"] = str(inspector_id)
        elif "inspector_id" in data:
            out["inspector_id"] = None

        if existing is None and not merged.get("checked_on"):
            raise ValidationError("checked_on is required")

        return out

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        if "semi_product_id" in data and str(data["semi_product_id"]) != str(existing.get("semi_product_id")):
            raise ValidationError("semi_product_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)


__all__ = [
    "SlaughterArrivalService",
    "SlaughterProcessingService",
    "SlaughterSemiProductService",
    "SlaughterSemiProductShipmentService",
    "SlaughterQualityCheckService",
]
