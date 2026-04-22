from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from app.core.exceptions import ValidationError
from app.repositories.core import ClientDebtRepository
from app.repositories.incubation import (
    ChickShipmentRepository,
    IncubationBatchRepository,
    IncubationRunRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.incubation import (
    ChickShipmentReadSchema,
    IncubationBatchReadSchema,
    IncubationRunReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft
from app.services.units import resolve_measurement_unit_id


AUTO_CHICK_SHIPMENT_AR_MARKER_PREFIX = "[auto-chick-shipment-ar:"


def _build_auto_ar_marker(shipment_id: str) -> str:
    return f"{AUTO_CHICK_SHIPMENT_AR_MARKER_PREFIX}{shipment_id}]"


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
    return Decimal(str(raw_value or 0))


def _egg_key(production_id: str) -> str:
    return f"egg:{production_id}"


def _chick_run_key(run_id: str) -> str:
    return f"chick_run:{run_id}"


class ChickShipmentService(BaseService):
    read_schema = ChickShipmentReadSchema

    def __init__(self, repository: ChickShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        run_id = entity.get("run_id")
        movement_rows: list[StockMovementDraft] = []
        quantity = _as_decimal(entity.get("chicks_count"))
        if run_id is not None and quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_chick_run_key(str(run_id)),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="chick_shipments",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="chick_shipments",
            reference_id=str(entity["id"]),
            movements=movement_rows,
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
        quantity = _as_decimal(entity.get("chicks_count"))
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
        measurement_unit_id = await resolve_measurement_unit_id(
            self.repository.db, str(entity["organization_id"]), "dona",
        )

        payload: dict[str, Any] = {
            "organization_id": str(entity["organization_id"]),
            "department_id": str(entity["department_id"]),
            "client_id": str(entity["client_id"]),
            "item_type": "chick",
            "item_key": f"chick_shipment:{shipment_id}",
            "quantity": str(quantity),
            "unit": "dona",
            "measurement_unit_id": measurement_unit_id,
            "amount_total": str(amount_total),
            "amount_paid": str(amount_paid),
            "currency": str(entity.get("currency") or ""),
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

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)
        await self._sync_auto_ar(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)
        await self._sync_auto_ar(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="chick_shipments",
            reference_id=str(deleted_entity["id"]),
        )
        await self._delete_auto_ar(str(deleted_entity["id"]))


class IncubationBatchService(BaseService):
    read_schema = IncubationBatchReadSchema

    def __init__(self, repository: IncubationBatchRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        if data.get("production_id") is None:
            raise ValidationError("production_id is required for incubation batch")
        return data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "production_id" in data and data.get("production_id") is None:
            raise ValidationError("production_id is required for incubation batch")
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        production_id = entity.get("production_id")
        if production_id is None:
            return

        quantity = _as_decimal(entity.get("eggs_arrived"))
        movement_rows: list[StockMovementDraft] = []
        if quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="egg",
                    item_key=_egg_key(str(production_id)),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="incubation_batches",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("batch_code")) if entity.get("batch_code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="incubation_batches",
            reference_id=str(entity["id"]),
            movements=movement_rows,
        )

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="incubation_batches",
            reference_id=str(deleted_entity["id"]),
        )


class IncubationRunService(BaseService):
    read_schema = IncubationRunReadSchema

    def __init__(self, repository: IncubationRunRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _available_chicks(entity: Mapping[str, Any]) -> Decimal:
        hatched = _as_decimal(entity.get("chicks_hatched"))
        destroyed = _as_decimal(entity.get("chicks_destroyed"))
        available = hatched - destroyed
        if available <= 0:
            return Decimal("0")
        return available

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = self._available_chicks(entity)
        movement_rows: list[StockMovementDraft] = []
        if quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_chick_run_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["end_date"] or entity["start_date"]),
                    reference_table="incubation_runs",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="incubation_runs",
            reference_id=str(entity["id"]),
            movements=movement_rows,
        )

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="incubation_runs",
            reference_id=str(deleted_entity["id"]),
        )


__all__ = [
    "ChickShipmentService",
    "IncubationBatchService",
    "IncubationRunService",
]
