from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from app.core.exceptions import ValidationError
from app.repositories.finance import SupplierDebtRepository
from app.repositories.inventory import StockMovementRepository
from app.repositories.medicine import (
    MedicineBatchRepository,
    MedicineConsumptionRepository,
    MedicineTypeRepository,
)
from app.schemas.medicine import (
    MedicineBatchReadSchema,
    MedicineConsumptionReadSchema,
    MedicineTypeReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft
from app.services.units import resolve_measurement_unit_id


AUTO_MEDICINE_ARRIVAL_AP_MARKER_PREFIX = "[auto-medicine-arrival-ap:"


def _build_auto_ap_marker(batch_id: str) -> str:
    return f"{AUTO_MEDICINE_ARRIVAL_AP_MARKER_PREFIX}{batch_id}]"


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


def _medicine_key(batch_id: str) -> str:
    return f"medicine_batch:{batch_id}"


class MedicineBatchService(BaseService):
    read_schema = MedicineBatchReadSchema

    def __init__(self, repository: MedicineBatchRepository) -> None:
        super().__init__(repository=repository)

    async def _consumed_quantity(self, batch_id: str) -> Decimal:
        row = await self.repository.db.fetchval(
            "SELECT COALESCE(SUM(quantity), 0) FROM medicine_consumptions WHERE batch_id = $1",
            batch_id,
        )
        return Decimal(str(row or 0))

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        received_quantity = _as_decimal(next_data.get("received_quantity"))
        next_data["received_quantity"] = str(received_quantity)
        next_data["remaining_quantity"] = str(received_quantity)
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
        next_data.pop("remaining_quantity", None)
        new_received = _as_decimal(next_data.get("received_quantity", existing.get("received_quantity")))
        consumed = await self._consumed_quantity(str(entity_id))
        if new_received < consumed:
            raise ValidationError(
                "received_quantity cannot be less than already-consumed quantity",
            )
        next_data["received_quantity"] = str(new_received)
        next_data["remaining_quantity"] = str(
            (new_received - consumed).quantize(Decimal("0.001"))
        )
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
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("batch_code")) if entity.get("batch_code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_batches",
            reference_id=str(entity["id"]),
            movements=movement_rows,
        )

    async def _find_auto_ap_debt(self, batch_id: str) -> dict[str, Any] | None:
        marker = _build_auto_ap_marker(batch_id)
        row = await self.repository.db.fetchrow(
            """
            SELECT *
            FROM supplier_debts
            WHERE note LIKE $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            f"%{marker}%",
        )
        return dict(row) if row is not None else None

    async def _sync_auto_ap(self, entity: Mapping[str, Any]) -> None:
        batch_id = str(entity["id"])
        debt_repo = SupplierDebtRepository(self.repository.db)
        existing_debt = await self._find_auto_ap_debt(batch_id)

        supplier_client_id = entity.get("supplier_client_id")
        received_quantity = _as_decimal(entity.get("received_quantity"))
        unit_cost_raw = entity.get("unit_cost")
        currency_id_raw = entity.get("currency_id")
        currency_id = str(currency_id_raw) if currency_id_raw else None

        if (
            not supplier_client_id
            or unit_cost_raw is None
            or Decimal(str(unit_cost_raw or 0)) <= 0
            or received_quantity <= 0
            or not currency_id
        ):
            if existing_debt is not None:
                await debt_repo.delete_by_id(str(existing_debt["id"]))
            return

        unit_cost = Decimal(str(unit_cost_raw)).quantize(Decimal("0.01"))
        amount_total = (unit_cost * received_quantity).quantize(Decimal("0.01"))
        amount_paid = Decimal(str((existing_debt or {}).get("amount_paid") or 0)).quantize(Decimal("0.01"))
        if amount_paid > amount_total:
            raise ValidationError(
                "Cannot reduce medicine batch total below already recorded debt payments",
            )

        marker = _build_auto_ap_marker(batch_id)
        note = _compose_auto_debt_note(
            marker,
            (existing_debt or {}).get("note") if existing_debt else None,
        )
        status = _resolve_auto_debt_status(amount_total, amount_paid)
        issued_on = _as_date(entity["arrived_on"])
        measurement_unit_id = await resolve_measurement_unit_id(
            self.repository.db, str(entity["organization_id"]), str(entity.get("unit") or "pcs"),
        )

        payload: dict[str, Any] = {
            "organization_id": str(entity["organization_id"]),
            "department_id": str(entity["department_id"]),
            "client_id": str(supplier_client_id),
            "item_type": "medicine",
            "item_key": f"medicine_batch:{batch_id}",
            "quantity": str(received_quantity),
            "unit": str(entity.get("unit") or "pcs"),
            "measurement_unit_id": measurement_unit_id,
            "amount_total": str(amount_total),
            "amount_paid": str(amount_paid),
            "currency_id": currency_id,
            "issued_on": issued_on,
            "status": status,
            "note": note,
            "is_active": True,
        }

        if existing_debt is None:
            await debt_repo.create({"id": str(uuid4()), **payload})
        else:
            await debt_repo.update_by_id(str(existing_debt["id"]), payload)

    async def _delete_auto_ap(self, batch_id: str) -> None:
        existing_debt = await self._find_auto_ap_debt(batch_id)
        if existing_debt is None:
            return
        await SupplierDebtRepository(self.repository.db).delete_by_id(str(existing_debt["id"]))

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)
        await self._sync_auto_ap(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)
        await self._sync_auto_ap(after)

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
        await self._delete_auto_ap(str(deleted_entity["id"]))


class MedicineTypeService(BaseService):
    read_schema = MedicineTypeReadSchema

    def __init__(self, repository: MedicineTypeRepository) -> None:
        super().__init__(repository=repository)


class MedicineConsumptionService(CreatedByActorMixin, BaseService):
    read_schema = MedicineConsumptionReadSchema

    def __init__(self, repository: MedicineConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _get_batch_or_raise(self, batch_id: str) -> Mapping[str, Any]:
        batch = await MedicineBatchRepository(self.repository.db).get_by_id_optional(batch_id)
        if batch is None:
            raise ValidationError("batch_id is invalid")
        return batch

    async def _validate_factory_flock(
        self,
        flock_id: str,
        *,
        organization_id: str,
    ) -> None:
        row = await self.repository.db.fetchrow(
            "SELECT organization_id FROM factory_flocks WHERE id = $1",
            flock_id,
        )
        if row is None:
            raise ValidationError("factory_flock_id is invalid")
        if str(row["organization_id"]) != str(organization_id):
            raise ValidationError("factory_flock belongs to a different organization")

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        batch_id = next_data.get("batch_id")
        if batch_id is None:
            raise ValidationError("batch_id is required")
        batch = await self._get_batch_or_raise(str(batch_id))

        if str(batch["organization_id"]) != str(next_data.get("organization_id") or batch["organization_id"]):
            raise ValidationError("batch belongs to a different organization")
        next_data["organization_id"] = str(batch["organization_id"])

        department_raw = next_data.get("department_id")
        if department_raw is None or str(department_raw).strip() == "":
            next_data["department_id"] = str(batch["department_id"])
        elif str(department_raw) != str(batch["department_id"]):
            raise ValidationError("department_id must match the batch department")

        quantity = _as_decimal(next_data.get("quantity"))
        if quantity <= 0:
            raise ValidationError("quantity must be positive")
        batch_remaining = _as_decimal(batch.get("remaining_quantity"))
        if quantity > batch_remaining:
            raise ValidationError(
                "quantity exceeds batch remaining_quantity",
            )
        next_data["quantity"] = str(quantity)
        next_data["unit"] = str(next_data.get("unit") or batch.get("unit") or "pcs")

        flock_raw = next_data.get("factory_flock_id")
        if flock_raw is not None and str(flock_raw).strip() != "":
            await self._validate_factory_flock(
                str(flock_raw),
                organization_id=str(batch["organization_id"]),
            )
            next_data["factory_flock_id"] = str(flock_raw)
        else:
            next_data["factory_flock_id"] = None
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
        target_batch_id = str(next_data.get("batch_id") or existing["batch_id"])
        batch = await self._get_batch_or_raise(target_batch_id)

        if "organization_id" in next_data and str(next_data["organization_id"]) != str(batch["organization_id"]):
            raise ValidationError("organization_id must match the batch organization")
        next_data["organization_id"] = str(batch["organization_id"])

        if "department_id" in next_data and str(next_data["department_id"]) != str(batch["department_id"]):
            raise ValidationError("department_id must match the batch department")

        if "quantity" in next_data:
            quantity = _as_decimal(next_data["quantity"])
            if quantity <= 0:
                raise ValidationError("quantity must be positive")
            existing_qty = _as_decimal(existing.get("quantity"))
            batch_remaining = _as_decimal(batch.get("remaining_quantity"))
            same_batch = str(existing.get("batch_id")) == target_batch_id
            delta = (quantity - existing_qty) if same_batch else quantity
            if delta > batch_remaining:
                raise ValidationError(
                    "quantity exceeds batch remaining_quantity",
                )
            next_data["quantity"] = str(quantity)

        if "unit" in next_data and next_data["unit"]:
            next_data["unit"] = str(next_data["unit"])

        if "factory_flock_id" in next_data:
            flock_raw = next_data.get("factory_flock_id")
            if flock_raw is None or str(flock_raw).strip() == "":
                next_data["factory_flock_id"] = None
            else:
                await self._validate_factory_flock(
                    str(flock_raw),
                    organization_id=str(batch["organization_id"]),
                )
                next_data["factory_flock_id"] = str(flock_raw)
        return next_data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        batch = await self._get_batch_or_raise(str(entity["batch_id"]))
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=_medicine_key(str(entity["batch_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or batch.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="medicine_consumptions",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(batch["warehouse_id"]) if batch.get("warehouse_id") else None,
                    note=(
                        str(entity.get("purpose"))
                        if entity.get("purpose") is not None
                        else None
                    ),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="medicine_consumptions",
            reference_id=str(entity["id"]),
            movements=movements,
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
            reference_table="medicine_consumptions",
            reference_id=str(deleted_entity["id"]),
        )


__all__ = [
    "MedicineBatchService",
    "MedicineTypeService",
    "MedicineConsumptionService",
]
