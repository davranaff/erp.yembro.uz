from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.inventory import StockMovementRepository
from app.repositories.slaughter import (
    SlaughterArrivalRepository,
    SlaughterProcessingRepository,
    SlaughterSemiProductRepository,
    SlaughterSemiProductShipmentRepository,
)
from app.schemas.slaughter import (
    SlaughterArrivalReadSchema,
    SlaughterProcessingReadSchema,
    SlaughterSemiProductReadSchema,
    SlaughterSemiProductShipmentReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0)).quantize(Decimal("0.001"))


def _chick_arrival_key(chick_arrival_id: str) -> str:
    return f"chick_arrival:{chick_arrival_id}"


def _semi_product_key(semi_product_id: str) -> str:
    return f"semi_product:{semi_product_id}"


class SlaughterArrivalService(BaseService):
    read_schema = SlaughterArrivalReadSchema

    def __init__(self, repository: SlaughterArrivalRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        if data.get("chick_arrival_id") is None:
            raise ValidationError("chick_arrival_id is required for slaughter arrival")
        return data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "chick_arrival_id" in data and data.get("chick_arrival_id") is None:
            raise ValidationError("chick_arrival_id is required for slaughter arrival")
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        chick_arrival_id = entity.get("chick_arrival_id")
        if chick_arrival_id is None:
            return

        quantity = _as_decimal(entity.get("birds_count"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_chick_arrival_key(str(chick_arrival_id)),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="slaughter_arrivals",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
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


class SlaughterProcessingService(BaseService):
    read_schema = SlaughterProcessingReadSchema

    def __init__(self, repository: SlaughterProcessingRepository) -> None:
        super().__init__(repository=repository)


class SlaughterSemiProductService(BaseService):
    read_schema = SlaughterSemiProductReadSchema

    def __init__(self, repository: SlaughterSemiProductRepository) -> None:
        super().__init__(repository=repository)

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
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="slaughter_semi_product_shipments",
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
            reference_table="slaughter_semi_product_shipments",
            reference_id=str(deleted_entity["id"]),
        )


__all__ = [
    "SlaughterArrivalService",
    "SlaughterProcessingService",
    "SlaughterSemiProductService",
    "SlaughterSemiProductShipmentService",
]
