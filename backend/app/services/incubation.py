from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.incubation import (
    ChickShipmentRepository,
    FactoryMonthlyAnalyticsRepository,
    IncubationBatchRepository,
    IncubationMonthlyAnalyticsRepository,
    IncubationRunRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.incubation import (
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


class IncubationMonthlyAnalyticsService(BaseService):
    read_schema = IncubationMonthlyAnalyticsReadSchema

    def __init__(self, repository: IncubationMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


class FactoryMonthlyAnalyticsService(BaseService):
    read_schema = FactoryMonthlyAnalyticsReadSchema

    def __init__(self, repository: FactoryMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "ChickShipmentService",
    "IncubationBatchService",
    "IncubationRunService",
    "IncubationMonthlyAnalyticsService",
    "FactoryMonthlyAnalyticsService",
]
