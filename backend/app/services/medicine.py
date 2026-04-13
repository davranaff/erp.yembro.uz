from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.inventory import StockMovementRepository
from app.repositories.medicine import (
    MedicineArrivalRepository,
    MedicineBatchRepository,
    MedicineConsumptionRepository,
    MedicineTypeRepository,
)
from app.schemas.medicine import (
    MedicineArrivalReadSchema,
    MedicineBatchReadSchema,
    MedicineConsumptionReadSchema,
    MedicineTypeReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0)).quantize(Decimal("0.001"))


def _medicine_key(batch_id: str) -> str:
    return f"medicine_batch:{batch_id}"


class MedicineArrivalService(BaseService):
    read_schema = MedicineArrivalReadSchema

    def __init__(self, repository: MedicineArrivalRepository) -> None:
        super().__init__(repository=repository)


class MedicineBatchService(BaseService):
    read_schema = MedicineBatchReadSchema

    def __init__(self, repository: MedicineBatchRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        received_quantity = _as_decimal(next_data.get("received_quantity"))
        remaining_quantity = (
            _as_decimal(next_data.get("remaining_quantity"))
            if next_data.get("remaining_quantity") is not None
            else received_quantity
        )
        if remaining_quantity > received_quantity:
            raise ValidationError("remaining_quantity cannot be greater than received_quantity")
        next_data["received_quantity"] = str(received_quantity)
        next_data["remaining_quantity"] = str(remaining_quantity)
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        new_received = _as_decimal(next_data.get("received_quantity", existing.get("received_quantity")))
        new_remaining = _as_decimal(next_data.get("remaining_quantity", existing.get("remaining_quantity")))

        if new_remaining > new_received:
            raise ValidationError("remaining_quantity cannot be greater than received_quantity")

        consumed_row = await self.repository.db.fetchrow(
            """
            SELECT COALESCE(SUM(quantity), 0) AS consumed
            FROM medicine_consumptions
            WHERE batch_id = $1
            """,
            entity_id,
        )
        consumed = _as_decimal(consumed_row["consumed"] if consumed_row is not None else 0)
        if new_received < consumed:
            raise ValidationError(
                f"received_quantity cannot be lower than already consumed quantity ({consumed})"
            )

        next_data["received_quantity"] = str(new_received)
        next_data["remaining_quantity"] = str(new_remaining)
        return next_data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        received_quantity = _as_decimal(entity.get("received_quantity"))
        movement_rows: list[StockMovementDraft] = []
        if received_quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=_medicine_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=received_quantity,
                    unit=str(entity.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="medicine_batches",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("batch_code")) if entity.get("batch_code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_batches",
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
            reference_table="medicine_batches",
            reference_id=str(deleted_entity["id"]),
        )


class MedicineConsumptionService(CreatedByActorMixin, BaseService):
    read_schema = MedicineConsumptionReadSchema

    def __init__(self, repository: MedicineConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _reserve_batch_quantity(
        self,
        *,
        batch_id: str,
        organization_id: str,
        department_id: str,
        quantity: Decimal,
        consumed_on: date,
    ) -> None:
        reserved_row = await self.repository.db.fetchrow(
            """
            UPDATE medicine_batches
            SET remaining_quantity = remaining_quantity - $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
              AND organization_id = $3
              AND department_id = $4
              AND remaining_quantity >= $5
              AND (expiry_date IS NULL OR expiry_date >= $6)
            RETURNING id
            """,
            str(quantity),
            batch_id,
            organization_id,
            department_id,
            str(quantity),
            consumed_on,
        )
        if reserved_row is not None:
            return

        batch = await self.repository.db.fetchrow(
            """
            SELECT id, organization_id, department_id, remaining_quantity, expiry_date
            FROM medicine_batches
            WHERE id = $1
            LIMIT 1
            """,
            batch_id,
        )
        if batch is None:
            raise ValidationError("batch_id is invalid")
        if str(batch["organization_id"]) != organization_id:
            raise ValidationError("batch belongs to another organization")
        if str(batch["department_id"]) != department_id:
            raise ValidationError("batch belongs to another department")
        if batch["expiry_date"] is not None and _as_date(batch["expiry_date"]) < consumed_on:
            raise ValidationError("Cannot consume expired medicine batch")

        available = _as_decimal(batch["remaining_quantity"])
        raise ValidationError(
            f"Consumption exceeds remaining batch quantity. Available={available}, requested={quantity}."
        )

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        batch_id = str(next_data.get("batch_id") or "").strip()
        if not batch_id:
            raise ValidationError("batch_id is required")

        quantity = _as_decimal(next_data.get("quantity"))
        if quantity <= 0:
            raise ValidationError("quantity must be positive")

        consumed_on = _as_date(next_data.get("consumed_on") or date.today())
        next_data["consumed_on"] = consumed_on
        next_data["quantity"] = str(quantity)

        organization_id = str(next_data.get("organization_id") or actor.organization_id)
        department_id = str(next_data.get("department_id") or actor.department_id or "").strip()
        if not department_id:
            raise ValidationError("department_id is required")

        await self._reserve_batch_quantity(
            batch_id=batch_id,
            organization_id=organization_id,
            department_id=department_id,
            quantity=quantity,
            consumed_on=consumed_on,
        )
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        immutable_fields = {
            "batch_id",
            "quantity",
            "consumed_on",
            "organization_id",
            "department_id",
        }
        for field in immutable_fields:
            if field in data:
                raise ValidationError(
                    "batch_id, quantity, consumed_on, organization_id, department_id are immutable for consumption records"
                )
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movement_rows: list[StockMovementDraft] = []
        if quantity > 0:
            movement_rows.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=_medicine_key(str(entity["batch_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="medicine_consumptions",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("purpose")) if entity.get("purpose") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_consumptions",
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
        quantity = _as_decimal(deleted_entity.get("quantity"))
        await self.repository.db.execute(
            """
            UPDATE medicine_batches
            SET remaining_quantity = remaining_quantity + $1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            """,
            str(quantity),
            deleted_entity.get("batch_id"),
        )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="medicine_consumptions",
            reference_id=str(deleted_entity["id"]),
        )


class MedicineTypeService(BaseService):
    read_schema = MedicineTypeReadSchema

    def __init__(self, repository: MedicineTypeRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "MedicineArrivalService",
    "MedicineBatchService",
    "MedicineConsumptionService",
    "MedicineTypeService",
]
