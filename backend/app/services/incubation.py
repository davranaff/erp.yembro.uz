from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.incubation import (
    ChickArrivalRepository,
    ChickShipmentRepository,
    FactoryMonthlyAnalyticsRepository,
    IncubationBatchRepository,
    IncubationMonthlyAnalyticsRepository,
    IncubationRunRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.incubation import (
    ChickArrivalReadSchema,
    ChickShipmentReadSchema,
    FactoryMonthlyAnalyticsReadSchema,
    IncubationBatchReadSchema,
    IncubationMonthlyAnalyticsReadSchema,
    IncubationRunReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft


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


def _chick_arrival_key(arrival_id: str) -> str:
    return f"chick_arrival:{arrival_id}"


class ChickArrivalService(BaseService):
    read_schema = ChickArrivalReadSchema

    def __init__(self, repository: ChickArrivalRepository) -> None:
        super().__init__(repository=repository)

    async def _fetch_run(self, run_id: str) -> Mapping[str, Any] | None:
        return await self.repository.db.fetchrow(
            """
            SELECT id, organization_id, department_id
            FROM incubation_runs
            WHERE id = $1
            LIMIT 1
            """,
            run_id,
        )

    async def _validate_arrival_source(
        self,
        *,
        organization_id: str,
        run_id: str | None,
        chick_shipment_id: str | None,
        quantity: Decimal,
        current_arrival_id: str | None = None,
    ) -> Mapping[str, Any] | None:
        if not run_id and not chick_shipment_id:
            raise ValidationError("Either run_id or chick_shipment_id is required")

        run_row: Mapping[str, Any] | None = None
        if run_id:
            run_row = await self._fetch_run(run_id)
            if run_row is None:
                raise ValidationError("run_id is invalid")
            if str(run_row["organization_id"]) != organization_id:
                raise ValidationError("run_id belongs to another organization")

        if chick_shipment_id:
            shipment_row = await self.repository.db.fetchrow(
                """
                SELECT id, organization_id, chicks_count
                FROM chick_shipments
                WHERE id = $1
                LIMIT 1
                """,
                chick_shipment_id,
            )
            if shipment_row is None:
                raise ValidationError("chick_shipment_id is invalid")
            if str(shipment_row["organization_id"]) != organization_id:
                raise ValidationError("chick_shipment_id belongs to another organization")

            consumed_row = await self.repository.db.fetchrow(
                """
                SELECT COALESCE(SUM(chicks_count), 0) AS consumed
                FROM chick_arrivals
                WHERE chick_shipment_id = $1
                  AND ($2 IS NULL OR id <> $3)
                """,
                chick_shipment_id,
                current_arrival_id,
                current_arrival_id,
            )
            consumed = _as_decimal(consumed_row["consumed"] if consumed_row is not None else 0)
            shipment_total = _as_decimal(shipment_row["chicks_count"])
            available = shipment_total - consumed
            if quantity > available:
                raise ValidationError(
                    f"Arrival exceeds shipment balance. Available={available}, requested={quantity}."
                )

        return run_row

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        organization_id = str(data.get("organization_id") or actor.organization_id)
        run_id = str(data.get("run_id")) if data.get("run_id") else None
        chick_shipment_id = str(data.get("chick_shipment_id")) if data.get("chick_shipment_id") else None
        quantity = _as_decimal(data.get("chicks_count"))

        await self._validate_arrival_source(
            organization_id=organization_id,
            run_id=run_id,
            chick_shipment_id=chick_shipment_id,
            quantity=quantity,
        )
        return data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        organization_id = str(existing.get("organization_id") or actor.organization_id)
        run_id = (
            str(data.get("run_id"))
            if "run_id" in data and data.get("run_id") is not None
            else str(existing.get("run_id"))
            if existing.get("run_id") is not None
            else None
        )
        chick_shipment_id = (
            str(data.get("chick_shipment_id"))
            if "chick_shipment_id" in data and data.get("chick_shipment_id") is not None
            else str(existing.get("chick_shipment_id"))
            if existing.get("chick_shipment_id") is not None
            else None
        )
        quantity = _as_decimal(data.get("chicks_count", existing.get("chicks_count")))

        await self._validate_arrival_source(
            organization_id=organization_id,
            run_id=run_id,
            chick_shipment_id=chick_shipment_id,
            quantity=quantity,
            current_arrival_id=str(entity_id),
        )
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("chicks_count"))
        movement_rows: list[StockMovementDraft] = []
        if quantity > 0:
            organization_id = str(entity["organization_id"])
            arrival_department_id = str(entity["department_id"])
            arrived_on = _as_date(entity["arrived_on"])

            run_id = entity.get("run_id")
            if run_id is not None:
                run_row = await self._fetch_run(str(run_id))
                if run_row is None:
                    raise ValidationError("run_id is invalid")
                run_department_id = str(run_row["department_id"])
                movement_rows.append(
                    StockMovementDraft(
                        organization_id=organization_id,
                        department_id=run_department_id,
                        counterparty_department_id=arrival_department_id,
                        item_type="chick",
                        item_key=_chick_run_key(str(run_id)),
                        movement_kind="transfer_out",
                        quantity=quantity,
                        unit="pcs",
                        occurred_on=arrived_on,
                        reference_table="chick_arrivals",
                        reference_id=str(entity["id"]),
                        note="Transfer from incubation run",
                    )
                )

            movement_rows.append(
                StockMovementDraft(
                    organization_id=organization_id,
                    department_id=arrival_department_id,
                    item_type="chick",
                    item_key=_chick_arrival_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=arrived_on,
                    reference_table="chick_arrivals",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="chick_arrivals",
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
            reference_table="chick_arrivals",
            reference_id=str(deleted_entity["id"]),
        )


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
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="chick_shipments",
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
            reference_table="chick_shipments",
            reference_id=str(deleted_entity["id"]),
        )


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


class IncubationMonthlyAnalyticsService(BaseService):
    read_schema = IncubationMonthlyAnalyticsReadSchema

    def __init__(self, repository: IncubationMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


class FactoryMonthlyAnalyticsService(BaseService):
    read_schema = FactoryMonthlyAnalyticsReadSchema

    def __init__(self, repository: FactoryMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "ChickArrivalService",
    "ChickShipmentService",
    "IncubationBatchService",
    "IncubationRunService",
    "IncubationMonthlyAnalyticsService",
    "FactoryMonthlyAnalyticsService",
]
