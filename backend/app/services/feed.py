from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping

from app.core.exceptions import ConflictError, ValidationError
from app.repositories.feed import (
    FeedArrivalRepository,
    FeedConsumptionRepository,
    FeedFormulaIngredientRepository,
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedProductionBatchRepository,
    FeedProductShipmentRepository,
    FeedRawArrivalRepository,
    FeedRawConsumptionRepository,
    FeedTypeRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.feed import (
    FeedArrivalReadSchema,
    FeedConsumptionReadSchema,
    FeedFormulaIngredientReadSchema,
    FeedFormulaReadSchema,
    FeedIngredientReadSchema,
    FeedProductionBatchReadSchema,
    FeedProductShipmentReadSchema,
    FeedRawArrivalReadSchema,
    FeedRawConsumptionReadSchema,
    FeedTypeReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0)).quantize(Decimal("0.001"))


def _feed_product_key(feed_type_id: str) -> str:
    return f"feed_product:{feed_type_id}"


def _feed_raw_key(ingredient_id: str) -> str:
    return f"feed_raw:{ingredient_id}"


class FeedTypeService(BaseService):
    read_schema = FeedTypeReadSchema

    def __init__(self, repository: FeedTypeRepository) -> None:
        super().__init__(repository=repository)


class FeedIngredientService(BaseService):
    read_schema = FeedIngredientReadSchema

    def __init__(self, repository: FeedIngredientRepository) -> None:
        super().__init__(repository=repository)

    async def _raise_if_has_dependencies(self, entity_id: Any) -> None:
        dependency_row = await self.repository.db.fetchrow(
            """
            SELECT
                (SELECT COUNT(*) FROM feed_formula_ingredients WHERE ingredient_id = $1) AS formula_items_count,
                (SELECT COUNT(*) FROM feed_raw_arrivals WHERE ingredient_id = $2) AS raw_arrivals_count,
                (SELECT COUNT(*) FROM feed_raw_consumptions WHERE ingredient_id = $3) AS raw_consumptions_count
            """,
            entity_id,
            entity_id,
            entity_id,
        )
        if dependency_row is None:
            return

        dependency_labels = {
            "formula_items_count": "formula ingredients",
            "raw_arrivals_count": "raw arrivals",
            "raw_consumptions_count": "raw consumptions",
        }
        active_dependencies: list[str] = []

        for field_name, label in dependency_labels.items():
            dependency_count = int(dependency_row[field_name] or 0)
            if dependency_count <= 0:
                continue
            active_dependencies.append(f"{label} ({dependency_count})")

        if not active_dependencies:
            return

        raise ConflictError(
            "Cannot delete this ingredient because it is still used in "
            + ", ".join(active_dependencies)
            + "."
        )

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None):
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        await self._raise_if_has_dependencies(entity_id)
        return await super().delete(entity_id, actor=actor)


class FeedArrivalService(BaseService):
    read_schema = FeedArrivalReadSchema

    def __init__(self, repository: FeedArrivalRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_product_key(str(entity["feed_type_id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="feed_arrivals",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_arrivals",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(reference_table="feed_arrivals", reference_id=str(deleted_entity["id"]))


class FeedConsumptionService(BaseService):
    read_schema = FeedConsumptionReadSchema

    def __init__(self, repository: FeedConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_product_key(str(entity["feed_type_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="feed_consumptions",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_consumptions",
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
            reference_table="feed_consumptions",
            reference_id=str(deleted_entity["id"]),
        )


class FeedFormulaService(BaseService):
    read_schema = FeedFormulaReadSchema

    def __init__(self, repository: FeedFormulaRepository) -> None:
        super().__init__(repository=repository)


class FeedFormulaIngredientService(BaseService):
    read_schema = FeedFormulaIngredientReadSchema

    def __init__(self, repository: FeedFormulaIngredientRepository) -> None:
        super().__init__(repository=repository)


class FeedRawArrivalService(BaseService):
    read_schema = FeedRawArrivalReadSchema

    def __init__(self, repository: FeedRawArrivalRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_raw_key(str(entity["ingredient_id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="feed_raw_arrivals",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("lot_no")) if entity.get("lot_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_raw_arrivals",
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
            reference_table="feed_raw_arrivals",
            reference_id=str(deleted_entity["id"]),
        )


class FeedProductionBatchService(BaseService):
    read_schema = FeedProductionBatchReadSchema

    def __init__(self, repository: FeedProductionBatchRepository) -> None:
        super().__init__(repository=repository)

    async def _fetch_formula_feed_type_id(self, formula_id: str) -> str:
        row = await self.repository.db.fetchrow(
            """
            SELECT feed_type_id
            FROM feed_formulas
            WHERE id = $1
            LIMIT 1
            """,
            formula_id,
        )
        if row is None:
            raise ValidationError("formula_id is invalid")
        return str(row["feed_type_id"])

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("actual_output"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            feed_type_id = await self._fetch_formula_feed_type_id(str(entity["formula_id"]))
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_product_key(feed_type_id),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity.get("finished_on") or entity.get("started_on")),
                    reference_table="feed_production_batches",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("batch_code")) if entity.get("batch_code") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_production_batches",
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
            reference_table="feed_production_batches",
            reference_id=str(deleted_entity["id"]),
        )


class FeedRawConsumptionService(BaseService):
    read_schema = FeedRawConsumptionReadSchema

    def __init__(self, repository: FeedRawConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_raw_key(str(entity["ingredient_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="feed_raw_consumptions",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_raw_consumptions",
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
            reference_table="feed_raw_consumptions",
            reference_id=str(deleted_entity["id"]),
        )


class FeedProductShipmentService(BaseService):
    read_schema = FeedProductShipmentReadSchema

    def __init__(self, repository: FeedProductShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_product_key(str(entity["feed_type_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="feed_product_shipments",
                    reference_id=str(entity["id"]),
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_product_shipments",
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
            reference_table="feed_product_shipments",
            reference_id=str(deleted_entity["id"]),
        )


__all__ = [
    "FeedTypeService",
    "FeedIngredientService",
    "FeedArrivalService",
    "FeedConsumptionService",
    "FeedFormulaService",
    "FeedFormulaIngredientService",
    "FeedRawArrivalService",
    "FeedProductionBatchService",
    "FeedRawConsumptionService",
    "FeedProductShipmentService",
]
