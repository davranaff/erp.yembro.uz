from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.egg import (
    EggMonthlyAnalyticsRepository,
    EggProductionRepository,
    EggShipmentRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.egg import (
    EggMonthlyAnalyticsReadSchema,
    EggProductionReadSchema,
    EggShipmentReadSchema,
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


class EggProductionService(BaseService):
    read_schema = EggProductionReadSchema

    def __init__(self, repository: EggProductionRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _net_eggs(entity: Mapping[str, Any]) -> Decimal:
        eggs_collected = _as_decimal(entity.get("eggs_collected"))
        eggs_broken = _as_decimal(entity.get("eggs_broken"))
        eggs_rejected = _as_decimal(entity.get("eggs_rejected"))
        net = eggs_collected - eggs_broken - eggs_rejected
        if net <= 0:
            return Decimal("0")
        return net

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = self._net_eggs(entity)
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="egg",
                    item_key=_egg_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["produced_on"]),
                    reference_table="egg_production",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        await ledger.replace_reference_movements(
            reference_table="egg_production",
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
            reference_table="egg_production",
            reference_id=str(deleted_entity["id"]),
        )


class EggShipmentService(BaseService):
    read_schema = EggShipmentReadSchema

    def __init__(self, repository: EggShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        if data.get("production_id") is None:
            raise ValidationError("production_id is required for egg shipment")
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
            raise ValidationError("production_id is required for egg shipment")
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        production_id = entity.get("production_id")
        if production_id is None:
            return

        quantity = _as_decimal(entity.get("eggs_count"))
        if quantity <= 0:
            movements: list[StockMovementDraft] = []
        else:
            movements = [
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="egg",
                    item_key=_egg_key(str(production_id)),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="egg_shipments",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            ]

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="egg_shipments",
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
            reference_table="egg_shipments",
            reference_id=str(deleted_entity["id"]),
        )


class EggMonthlyAnalyticsService(BaseService):
    read_schema = EggMonthlyAnalyticsReadSchema

    def __init__(self, repository: EggMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "EggProductionService",
    "EggShipmentService",
    "EggMonthlyAnalyticsService",
]
