from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping

from app.core.exceptions import ValidationError
from app.repositories.factory import (
    FactoryDailyLogRepository,
    FactoryFlockRepository,
    FactoryMedicineUsageRepository,
    FactoryShipmentRepository,
    FactoryVaccinationPlanRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.factory import (
    FactoryDailyLogReadSchema,
    FactoryFlockReadSchema,
    FactoryMedicineUsageReadSchema,
    FactoryShipmentReadSchema,
    FactoryVaccinationPlanReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_int(raw_value: object) -> int:
    return int(raw_value or 0)


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0))


def _flock_key(flock_id: str) -> str:
    return f"factory_flock:{flock_id}"


# ---------------------------------------------------------------------------
# Flock service
# ---------------------------------------------------------------------------


class FactoryFlockService(BaseService):
    read_schema = FactoryFlockReadSchema

    def __init__(self, repository: FactoryFlockRepository) -> None:
        super().__init__(repository=repository)

    async def _validate_chick_arrival(
        self,
        chick_arrival_id: Any,
        organization_id: Any,
    ) -> None:
        row = await self.repository.db.fetchrow(
            "SELECT organization_id FROM chick_arrivals WHERE id = $1",
            str(chick_arrival_id),
        )
        if row is None:
            raise ValidationError("chick_arrival_id is invalid")
        if str(row["organization_id"]) != str(organization_id):
            raise ValidationError("chick_arrival belongs to a different organization")

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        initial_count = _as_int(next_data.get("initial_count"))
        if initial_count <= 0:
            raise ValidationError("initial_count must be positive")
        if next_data.get("current_count") is None:
            next_data["current_count"] = initial_count
        chick_arrival_id = next_data.get("chick_arrival_id")
        if chick_arrival_id:
            await self._validate_chick_arrival(chick_arrival_id, next_data.get("organization_id"))
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
        new_initial = _as_int(next_data.get("initial_count", existing.get("initial_count")))
        new_current = _as_int(next_data.get("current_count", existing.get("current_count")))
        if new_current > new_initial:
            raise ValidationError("current_count cannot exceed initial_count")
        if "chick_arrival_id" in next_data and next_data["chick_arrival_id"]:
            await self._validate_chick_arrival(
                next_data["chick_arrival_id"],
                next_data.get("organization_id", existing.get("organization_id")),
            )
        return next_data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_int(entity.get("initial_count"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_flock_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=Decimal(quantity),
                    unit="pcs",
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="factory_flocks",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=str(entity.get("flock_code")) if entity.get("flock_code") else None,
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="factory_flocks",
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
            reference_table="factory_flocks",
            reference_id=str(deleted_entity["id"]),
        )


# ---------------------------------------------------------------------------
# Daily log service
# ---------------------------------------------------------------------------


class FactoryDailyLogService(BaseService):
    read_schema = FactoryDailyLogReadSchema

    def __init__(self, repository: FactoryDailyLogRepository) -> None:
        super().__init__(repository=repository)

    async def _check_feed_balance(
        self,
        *,
        organization_id: str,
        department_id: str,
        warehouse_id: str | None,
        feed_type_id: str,
        needed: Decimal,
        occurred_on: date,
        exclude_daily_log_id: str | None = None,
    ) -> None:
        if needed <= 0:
            return
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        balance = await ledger.get_balance(
            organization_id=organization_id,
            department_id=department_id,
            warehouse_id=warehouse_id,
            item_type="feed",
            item_key=f"feed_product:{feed_type_id}",
            as_of=occurred_on,
        )
        if exclude_daily_log_id is not None:
            own = await self.repository.db.fetchrow(
                """
                SELECT COALESCE(SUM(quantity), 0) AS q
                FROM stock_movements
                WHERE reference_table = 'factory_daily_logs'
                  AND reference_id = $1
                  AND movement_kind = 'outgoing'
                """,
                exclude_daily_log_id,
            )
            if own is not None:
                balance = balance + Decimal(str(own["q"] or 0))
        if balance < needed:
            raise ValidationError(
                f"Недостаточно корма для суточного расхода: "
                f"нужно {needed} кг, на складе {balance} кг"
            )

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        mortality = _as_int(next_data.get("mortality_count"))
        if mortality < 0:
            raise ValidationError("mortality_count cannot be negative")
        sick = _as_int(next_data.get("sick_count"))
        if sick < 0:
            raise ValidationError("sick_count cannot be negative")
        # Auto-calculate healthy_count if not provided
        if next_data.get("healthy_count") is None:
            flock_id = str(next_data.get("flock_id", ""))
            if flock_id:
                flock = await self.repository.db.fetchrow(
                    "SELECT current_count FROM factory_flocks WHERE id = $1",
                    flock_id,
                )
                if flock:
                    next_data["healthy_count"] = max(int(flock["current_count"]) - mortality - sick, 0)
                else:
                    next_data["healthy_count"] = 0
            else:
                next_data["healthy_count"] = 0
        # Pre-check feed balance — not allow consuming more than available.
        feed_consumed = _as_decimal(next_data.get("feed_consumed_kg"))
        feed_type_id = next_data.get("feed_type_id")
        organization_id = str(next_data.get("organization_id") or "").strip()
        if not organization_id and actor is not None:
            organization_id = actor.organization_id
        department_id = str(next_data.get("department_id") or "").strip()
        occurred_on = _as_date(next_data.get("log_date") or date.today())
        if feed_consumed > 0 and feed_type_id and organization_id and department_id:
            await self._check_feed_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=None,
                feed_type_id=str(feed_type_id),
                needed=feed_consumed,
                occurred_on=occurred_on,
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
        next_data = dict(data)
        merged = {**existing, **next_data}
        feed_consumed = _as_decimal(merged.get("feed_consumed_kg"))
        feed_type_id = merged.get("feed_type_id")
        organization_id = str(merged.get("organization_id") or "")
        department_id = str(merged.get("department_id") or "")
        occurred_on = _as_date(merged.get("log_date") or date.today())
        if feed_consumed > 0 and feed_type_id and organization_id and department_id:
            await self._check_feed_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=None,
                feed_type_id=str(feed_type_id),
                needed=feed_consumed,
                occurred_on=occurred_on,
                exclude_daily_log_id=str(entity_id),
            )
        return next_data

    async def _sync_feed_consumption_row(self, entity: Mapping[str, Any]) -> None:
        """Mirror daily log's feed entry into a feed_consumptions row.

        Why: ``factory_daily_logs.feed_consumed_kg`` and ``feed_consumptions``
        used to be independent inputs — analytics that read feed_consumptions
        missed daily-log consumption (and vice versa), or double-counted when
        both existed. We keep a single derived row per daily log, keyed by
        ``daily_log_id`` (unique).
        """
        db = self.repository.db
        daily_log_id = str(entity["id"])
        feed_consumed = _as_decimal(entity.get("feed_consumed_kg"))
        feed_type_id = entity.get("feed_type_id")

        if feed_consumed <= 0 or not feed_type_id:
            await db.execute(
                "DELETE FROM feed_consumptions WHERE daily_log_id = $1",
                daily_log_id,
            )
            return

        flock_row = await db.fetchrow(
            "SELECT poultry_type_id FROM factory_flocks WHERE id = $1",
            str(entity["flock_id"]),
        )
        poultry_type_id = (
            str(flock_row["poultry_type_id"])
            if flock_row is not None and flock_row["poultry_type_id"] is not None
            else None
        )

        note = entity.get("note")
        await db.execute(
            """
            INSERT INTO feed_consumptions (
                id, organization_id, department_id, poultry_type_id,
                feed_type_id, daily_log_id, consumed_on, quantity, unit, note,
                created_at, updated_at
            )
            VALUES (gen_random_uuid(), $1, $2, $3, $4, $5, $6, $7, 'kg', $8, now(), now())
            ON CONFLICT (daily_log_id) DO UPDATE SET
                organization_id = EXCLUDED.organization_id,
                department_id = EXCLUDED.department_id,
                poultry_type_id = EXCLUDED.poultry_type_id,
                feed_type_id = EXCLUDED.feed_type_id,
                consumed_on = EXCLUDED.consumed_on,
                quantity = EXCLUDED.quantity,
                unit = EXCLUDED.unit,
                note = EXCLUDED.note,
                updated_at = now()
            """,
            str(entity["organization_id"]),
            str(entity["department_id"]),
            poultry_type_id,
            str(feed_type_id),
            daily_log_id,
            _as_date(entity["log_date"]),
            feed_consumed,
            note,
        )

    async def _sync_feed_stock(self, entity: Mapping[str, Any]) -> None:
        """Sync outgoing feed stock movement when feed is consumed."""
        feed_consumed = _as_decimal(entity.get("feed_consumed_kg"))
        feed_type_id = entity.get("feed_type_id")
        movements: list[StockMovementDraft] = []

        if feed_consumed > 0 and feed_type_id:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=f"feed_product:{feed_type_id}",
                    movement_kind="outgoing",
                    quantity=feed_consumed,
                    unit="kg",
                    occurred_on=_as_date(entity["log_date"]),
                    reference_table="factory_daily_logs",
                    reference_id=str(entity["id"]),
                    note=f"Flock feed consumption",
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="factory_daily_logs",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._recalculate_flock_count(str(entity["flock_id"]))
        await self._sync_feed_stock(entity)
        await self._sync_feed_consumption_row(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._recalculate_flock_count(str(after["flock_id"]))
        if str(before.get("flock_id")) != str(after.get("flock_id")):
            await self._recalculate_flock_count(str(before["flock_id"]))
        await self._sync_feed_stock(after)
        await self._sync_feed_consumption_row(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        await self._recalculate_flock_count(str(deleted_entity["flock_id"]))
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="factory_daily_logs",
            reference_id=str(deleted_entity["id"]),
        )

    async def _recalculate_flock_count(self, flock_id: str) -> None:
        total_mortality = await self.repository.db.fetchval(
            """
            SELECT COALESCE(SUM(mortality_count), 0)
            FROM factory_daily_logs
            WHERE flock_id = $1
            """,
            flock_id,
        )
        total_shipped = await self.repository.db.fetchval(
            """
            SELECT COALESCE(SUM(birds_count), 0)
            FROM factory_shipments
            WHERE flock_id = $1
            """,
            flock_id,
        )
        await self.repository.db.execute(
            """
            UPDATE factory_flocks
            SET current_count = GREATEST(initial_count - $1 - $2, 0),
                updated_at = now()
            WHERE id = $3
            """,
            int(total_mortality),
            int(total_shipped),
            flock_id,
        )


# ---------------------------------------------------------------------------
# Shipment service
# ---------------------------------------------------------------------------


class FactoryShipmentService(BaseService):
    read_schema = FactoryShipmentReadSchema

    def __init__(self, repository: FactoryShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self, data: dict[str, Any], *, actor=None
    ) -> dict[str, Any]:
        out = dict(data)
        birds_count = _as_int(out.get("birds_count"))
        flock_id = str(out.get("flock_id") or "").strip()
        if birds_count > 0 and flock_id:
            row = await self.repository.db.fetchrow(
                "SELECT current_count FROM factory_flocks WHERE id = $1",
                flock_id,
            )
            if row is None:
                raise ValidationError("flock not found")
            available = int(row["current_count"] or 0)
            if available < birds_count:
                raise ValidationError(
                    f"Недостаточно птицы в flock: нужно {birds_count}, "
                    f"доступно {available}"
                )
        return out

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        out = dict(data)
        merged = {**existing, **out}
        birds_count = _as_int(merged.get("birds_count"))
        flock_id = str(merged.get("flock_id") or "").strip()
        if birds_count > 0 and flock_id:
            row = await self.repository.db.fetchrow(
                "SELECT current_count FROM factory_flocks WHERE id = $1",
                flock_id,
            )
            if row is None:
                raise ValidationError("flock not found")
            available = int(row["current_count"] or 0)
            # При редактировании собственного shipment учитываем, что
            # его старое списание уже уменьшило current_count.
            prior = _as_int(existing.get("birds_count"))
            net_need = birds_count - prior
            if net_need > available:
                raise ValidationError(
                    f"Недостаточно птицы: дополнительно нужно {net_need}, "
                    f"доступно {available}"
                )
        return out

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        """Outgoing пишется только после подтверждения получения."""
        birds_count = _as_int(entity.get("birds_count"))
        status = str(entity.get("status") or "").strip().lower()
        is_confirmed = status == "received" or bool(entity.get("acknowledged_at"))
        movements: list[StockMovementDraft] = []
        if birds_count > 0 and is_confirmed:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="chick",
                    item_key=_flock_key(str(entity["flock_id"])),
                    movement_kind="outgoing",
                    quantity=Decimal(birds_count),
                    unit="pcs",
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="factory_shipments",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=str(entity.get("invoice_no")) if entity.get("invoice_no") else None,
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="factory_shipments",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_stock(entity)
        await self._recalculate_flock_count(str(entity["flock_id"]))

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_stock(after)
        await self._recalculate_flock_count(str(after["flock_id"]))
        if str(before.get("flock_id")) != str(after.get("flock_id")):
            await self._recalculate_flock_count(str(before["flock_id"]))

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="factory_shipments",
            reference_id=str(deleted_entity["id"]),
        )
        await self._recalculate_flock_count(str(deleted_entity["flock_id"]))

    async def _recalculate_flock_count(self, flock_id: str) -> None:
        total_mortality = await self.repository.db.fetchval(
            """
            SELECT COALESCE(SUM(mortality_count), 0)
            FROM factory_daily_logs
            WHERE flock_id = $1
            """,
            flock_id,
        )
        total_shipped = await self.repository.db.fetchval(
            """
            SELECT COALESCE(SUM(birds_count), 0)
            FROM factory_shipments
            WHERE flock_id = $1
            """,
            flock_id,
        )
        await self.repository.db.execute(
            """
            UPDATE factory_flocks
            SET current_count = GREATEST(initial_count - $1 - $2, 0),
                updated_at = now()
            WHERE id = $3
            """,
            int(total_mortality),
            int(total_shipped),
            flock_id,
        )


# ---------------------------------------------------------------------------
# Medicine usage service
# ---------------------------------------------------------------------------


class FactoryMedicineUsageService(BaseService):
    read_schema = FactoryMedicineUsageReadSchema

    def __init__(self, repository: FactoryMedicineUsageRepository) -> None:
        super().__init__(repository=repository)

    async def _check_medicine_balance(
        self,
        *,
        organization_id: str,
        department_id: str,
        warehouse_id: str | None,
        medicine_type_id: str,
        needed: Decimal,
        occurred_on: date,
        exclude_usage_id: str | None = None,
    ) -> None:
        if needed <= 0:
            return
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        balance = await ledger.get_balance(
            organization_id=organization_id,
            department_id=department_id,
            warehouse_id=warehouse_id,
            item_type="medicine",
            item_key=f"medicine_usage:{medicine_type_id}",
            as_of=occurred_on,
        )
        if exclude_usage_id is not None:
            own = await self.repository.db.fetchrow(
                """
                SELECT COALESCE(SUM(quantity), 0) AS q
                FROM stock_movements
                WHERE reference_table = 'factory_medicine_usages'
                  AND reference_id = $1
                  AND movement_kind = 'outgoing'
                """,
                exclude_usage_id,
            )
            if own is not None:
                balance = balance + Decimal(str(own["q"] or 0))
        if balance < needed:
            raise ValidationError(
                f"Недостаточно лекарства: нужно {needed}, на складе {balance}"
            )

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        quantity = _as_decimal(next_data.get("quantity"))
        if quantity <= 0:
            raise ValidationError("quantity must be positive")
        organization_id = str(next_data.get("organization_id") or "").strip()
        if not organization_id and actor is not None:
            organization_id = actor.organization_id
        department_id = str(next_data.get("department_id") or "").strip()
        warehouse_id = (
            str(next_data["warehouse_id"]) if next_data.get("warehouse_id") else None
        )
        medicine_type_id = str(next_data.get("medicine_type_id") or "").strip()
        occurred_on = _as_date(next_data.get("usage_date") or date.today())
        if organization_id and department_id and medicine_type_id:
            await self._check_medicine_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                medicine_type_id=medicine_type_id,
                needed=quantity,
                occurred_on=occurred_on,
            )
        # Auto-calculate total_cost if unit_cost is provided
        unit_cost = next_data.get("unit_cost")
        if unit_cost is not None and next_data.get("total_cost") is None:
            next_data["total_cost"] = _as_decimal(unit_cost) * quantity
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
        merged = {**existing, **next_data}
        quantity = _as_decimal(merged.get("quantity"))
        organization_id = str(merged.get("organization_id") or "")
        department_id = str(merged.get("department_id") or "")
        warehouse_id = (
            str(merged["warehouse_id"]) if merged.get("warehouse_id") else None
        )
        medicine_type_id = str(merged.get("medicine_type_id") or "")
        occurred_on = _as_date(merged.get("usage_date") or date.today())
        if organization_id and department_id and medicine_type_id and quantity > 0:
            await self._check_medicine_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                medicine_type_id=medicine_type_id,
                needed=quantity,
                occurred_on=occurred_on,
                exclude_usage_id=str(entity_id),
            )
        unit_cost = next_data.get("unit_cost", existing.get("unit_cost"))
        if unit_cost is not None and next_data.get("total_cost") is None:
            next_data["total_cost"] = _as_decimal(unit_cost) * quantity
        return next_data

    async def _sync_medicine_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            medicine_type_id = str(entity.get("medicine_type_id", ""))
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="medicine",
                    item_key=f"medicine_usage:{medicine_type_id}",
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["usage_date"]),
                    reference_table="factory_medicine_usages",
                    reference_id=str(entity["id"]),
                    note=str(entity.get("note")) if entity.get("note") else None,
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="factory_medicine_usages",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(self, entity: Mapping[str, Any], *, actor=None) -> None:
        await self._sync_medicine_stock(entity)

    async def _after_update(self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None) -> None:
        await self._sync_medicine_stock(after)

    async def _after_delete(self, *, deleted_entity: Mapping[str, Any], actor=None) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="factory_medicine_usages",
            reference_id=str(deleted_entity["id"]),
        )


# ---------------------------------------------------------------------------
# Vaccination plan service
# ---------------------------------------------------------------------------


class FactoryVaccinationPlanService(BaseService):
    read_schema = FactoryVaccinationPlanReadSchema

    def __init__(self, repository: FactoryVaccinationPlanRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        day_of_life = _as_int(next_data.get("day_of_life"))
        if day_of_life <= 0:
            raise ValidationError("day_of_life must be positive")
        return next_data


__all__ = [
    "FactoryFlockService",
    "FactoryDailyLogService",
    "FactoryShipmentService",
    "FactoryMedicineUsageService",
    "FactoryVaccinationPlanService",
]
