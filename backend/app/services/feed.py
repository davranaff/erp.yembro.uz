from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping
from uuid import uuid4

from app.core.exceptions import AccessDeniedError, ConflictError, ValidationError
from app.repositories.core import (
    ClientDebtRepository,
    ClientRepository,
    WarehouseRepository,
)
from app.repositories.feed import (
    FeedConsumptionRepository,
    FeedFormulaIngredientRepository,
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedProductionBatchRepository,
    FeedProductionQualityCheckRepository,
    FeedProductShipmentRepository,
    FeedRawArrivalRepository,
    FeedRawConsumptionRepository,
    FeedTypeRepository,
)
from app.repositories.finance import SupplierDebtRepository
from app.repositories.hr import EmployeeRepository
from app.repositories.inventory import StockMovementRepository
from app.schemas.feed import (
    FeedConsumptionReadSchema,
    FeedFormulaIngredientReadSchema,
    FeedFormulaReadSchema,
    FeedIngredientReadSchema,
    FeedProductionBatchReadSchema,
    FeedProductionQualityCheckReadSchema,
    FeedProductShipmentReadSchema,
    FeedRawArrivalReadSchema,
    FeedRawConsumptionReadSchema,
    FeedTypeReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import StockLedgerService, StockMovementDraft

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


FEED_QUALITY_CHECK_STATUSES = ("pending", "passed", "failed")
FEED_QUALITY_CHECK_GRADES = ("first", "second", "mixed", "premium", "rejected")

AUTO_FEED_SHIPMENT_AR_MARKER_PREFIX = "[auto-feed-shipment-ar:"
AUTO_FEED_ARRIVAL_AP_MARKER_PREFIX = "[auto-feed-arrival-ap:"


def _build_auto_ar_marker(shipment_id: str) -> str:
    return f"{AUTO_FEED_SHIPMENT_AR_MARKER_PREFIX}{shipment_id}]"


def _build_auto_ap_marker(arrival_id: str) -> str:
    return f"{AUTO_FEED_ARRIVAL_AP_MARKER_PREFIX}{arrival_id}]"


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


def _normalize_currency(raw_value: object) -> str | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip().upper()
    return text or None


def _feed_product_key(production_batch_id: str) -> str:
    """Compose the stock-ledger item_key for a feed product tied to its production batch."""
    return f"feed_product:{production_batch_id}"


def _feed_product_key_by_type(feed_type_id: str) -> str:
    """Legacy item_key for stock rows that have no production_batch_id (e.g. factory daily logs).

    New code should always prefer :func:`_feed_product_key` when the batch is known,
    so balances can be computed per-batch and support FIFO/FEFO/recall.
    """
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

    async def delete(self, entity_id: Any, *, actor: "CurrentActor | None" = None):
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        await self._raise_if_has_dependencies(entity_id)
        return await super().delete(entity_id, actor=actor)


class FeedFormulaService(BaseService):
    read_schema = FeedFormulaReadSchema

    def __init__(self, repository: FeedFormulaRepository) -> None:
        super().__init__(repository=repository)


class FeedFormulaIngredientService(BaseService):
    """CRUD сервис для состава формулы.

    Простая обёртка без хуков: сам факт создания/удаления строки ни на
    что не влияет, пока пользователь не создаст production batch по этой
    формуле. Отдельные ручки (GET /feed/formulas/{id}/ingredients)
    собираются прямо в API слое без перегрузок сервиса.
    """

    read_schema = FeedFormulaIngredientReadSchema

    def __init__(self, repository: FeedFormulaIngredientRepository) -> None:
        super().__init__(repository=repository)


class FeedProductionBatchService(CreatedByActorMixin, BaseService):
    """Производство готового корма.

    При создании/обновлении batch'а сервис делает три вещи, которые
    раньше лежали на плечах оператора:

    1. **Проверяет наличие сырья**. Для каждого ингредиента формулы
       считает требуемое количество ``formula_ingredient.quantity_per_unit ×
       batch.planned_output`` и сравнивает с остатком на складе через
       ``StockLedgerService.get_balance``. Если не хватает — бросает
       ``ValidationError`` с деталями недостачи.

    2. **Списывает сырьё**. По ``actual_output`` (или ``planned_output``
       если фактического ещё нет) автоматически создаёт
       ``feed_raw_consumptions`` — по одной строке на каждый ингредиент
       формулы. Эти строки триггерят outgoing в ``stock_movements``
       через ``FeedRawConsumptionService._sync_stock`` и тем самым
       реально убирают сырьё со склада.

    3. **Считает себестоимость**. Для каждого израсходованного
       ингредиента берёт moving-average цену из ``feed_raw_arrivals``,
       умножает на израсходованное количество и складывает. Результат
       пишет в ``total_cost`` / ``unit_cost`` самой партии.
    """

    read_schema = FeedProductionBatchReadSchema

    def __init__(self, repository: FeedProductionBatchRepository) -> None:
        super().__init__(repository=repository)

    # ------------------ helpers ------------------

    async def _fetch_formula_ingredients(
        self, *, formula_id: str
    ) -> list[dict[str, Any]]:
        rows = await self.repository.db.fetch(
            """
            SELECT fi.id,
                   fi.formula_id,
                   fi.ingredient_id,
                   fi.quantity_per_unit,
                   fi.unit,
                   fi.measurement_unit_id,
                   i.name AS ingredient_name
            FROM feed_formula_ingredients fi
            JOIN feed_ingredients i ON i.id = fi.ingredient_id
            WHERE fi.formula_id = $1
            ORDER BY fi.sort_order ASC, i.name ASC
            """,
            formula_id,
        )
        return [dict(r) for r in rows]

    async def _compute_ingredient_avg_price(
        self,
        *,
        organization_id: str,
        ingredient_id: str,
    ) -> tuple[Decimal, str | None]:
        """Возвращает (средневзвешенная цена за единицу, currency_id).

        Цена считается как ``sum(qty × unit_price) / sum(qty)`` по всем
        приходам этого ингредиента, у которых указана ``unit_price``.
        Если приходов с ценой нет — возвращает (0, None).
        """

        row = await self.repository.db.fetchrow(
            """
            SELECT
                COALESCE(SUM(quantity * unit_price) / NULLIF(SUM(quantity), 0), 0) AS avg_price,
                (
                    SELECT currency_id
                    FROM feed_raw_arrivals
                    WHERE organization_id = $1
                      AND ingredient_id = $2
                      AND unit_price IS NOT NULL
                    ORDER BY arrived_on DESC, created_at DESC
                    LIMIT 1
                ) AS currency_id
            FROM feed_raw_arrivals
            WHERE organization_id = $1
              AND ingredient_id = $2
              AND unit_price IS NOT NULL
            """,
            organization_id,
            ingredient_id,
        )
        if row is None:
            return Decimal("0"), None
        avg_price = Decimal(str(row["avg_price"] or 0)).quantize(Decimal("0.0001"))
        currency_id = str(row["currency_id"]) if row["currency_id"] else None
        return avg_price, currency_id

    async def _check_availability(
        self,
        *,
        organization_id: str,
        department_id: str,
        warehouse_id: str | None,
        formula_id: str,
        required_output: Decimal,
        occurred_on: date,
        exclude_batch_id: str | None = None,
    ) -> None:
        """Бросает ``ValidationError`` если сырья не хватает.

        При обновлении batch'а передаётся ``exclude_batch_id`` — его
        собственные расходы исключаются из подсчёта баланса, чтобы
        проверка была «чистой» (иначе batch «конкурирует сам с собой»).
        """

        if required_output <= 0:
            return

        ingredients = await self._fetch_formula_ingredients(formula_id=formula_id)
        if not ingredients:
            raise ValidationError(
                "Formula has no ingredients configured — add ingredients first",
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        missing: list[str] = []
        for ing in ingredients:
            needed = (
                Decimal(str(ing["quantity_per_unit"])) * required_output
            ).quantize(Decimal("0.001"))
            balance = await ledger.get_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                item_type="feed_raw",
                item_key=_feed_raw_key(str(ing["ingredient_id"])),
                as_of=occurred_on,
            )
            # Если этот же batch уже имеет расходы — они уже "съели"
            # баланс, но при пересчёте мы хотим сравнить с "чистым"
            # состоянием без учёта этого batch'а.
            if exclude_batch_id is not None:
                own_used = await self.repository.db.fetchrow(
                    """
                    SELECT COALESCE(SUM(quantity), 0) AS q
                    FROM feed_raw_consumptions
                    WHERE production_batch_id = $1
                      AND ingredient_id = $2
                    """,
                    exclude_batch_id,
                    str(ing["ingredient_id"]),
                )
                if own_used is not None:
                    balance = balance + Decimal(str(own_used["q"] or 0))
            if balance < needed:
                missing.append(
                    f"{ing.get('ingredient_name') or ing['ingredient_id']}: "
                    f"нужно {needed}, на складе {balance}"
                )

        if missing:
            raise ValidationError(
                "Недостаточно сырья для производства: " + "; ".join(missing)
            )

    async def _resolve_measurement_unit_id(
        self, *, organization_id: str, unit_code: str
    ) -> str:
        from app.services.units import resolve_measurement_unit_id

        return await resolve_measurement_unit_id(
            self.repository.db, organization_id, (unit_code or "kg")
        )

    async def _rebuild_raw_consumptions(
        self, entity: Mapping[str, Any], *, actor=None
    ) -> tuple[Decimal, str | None]:
        """Пересоздаёт строки feed_raw_consumptions по формуле batch'а.

        Использует ``FeedRawConsumptionService`` напрямую, чтобы
        автоматически сработал его ``_sync_stock`` и ingredient списался
        со склада через ``stock_movements``. Возвращает кортеж
        (total_cost, currency_id) — для обновления полей batch'а.
        """

        batch_id = str(entity["id"])
        organization_id = str(entity["organization_id"])
        department_id = str(entity["department_id"])
        formula_id = str(entity["formula_id"])
        warehouse_id = (
            str(entity["warehouse_id"]) if entity.get("warehouse_id") else None
        )
        consumed_on = _as_date(
            entity.get("finished_on") or entity.get("started_on")
        )
        actual_output = _as_decimal(entity.get("actual_output"))

        raw_repo = FeedRawConsumptionRepository(self.repository.db)
        raw_service = FeedRawConsumptionService(raw_repo)

        # Сначала убираем все старые авто-расходы этого batch'а —
        # дальше создадим заново по актуальной формуле и output'у.
        existing = await self.repository.db.fetch(
            "SELECT id FROM feed_raw_consumptions WHERE production_batch_id = $1",
            batch_id,
        )
        for row in existing:
            await raw_service.delete(str(row["id"]), actor=actor)

        if actual_output <= 0:
            return Decimal("0.00"), None

        ingredients = await self._fetch_formula_ingredients(formula_id=formula_id)
        if not ingredients:
            return Decimal("0.00"), None

        total_cost = Decimal("0")
        currency_id: str | None = None

        for ing in ingredients:
            consumed_qty = (
                Decimal(str(ing["quantity_per_unit"])) * actual_output
            ).quantize(Decimal("0.001"))
            if consumed_qty <= 0:
                continue
            unit_code = str(ing.get("unit") or "kg")
            measurement_unit_id = str(ing["measurement_unit_id"])
            payload: dict[str, Any] = {
                "organization_id": organization_id,
                "department_id": department_id,
                "warehouse_id": warehouse_id,
                "production_batch_id": batch_id,
                "ingredient_id": str(ing["ingredient_id"]),
                "consumed_on": consumed_on,
                "quantity": str(consumed_qty),
                "unit": unit_code,
                "measurement_unit_id": measurement_unit_id,
                "note": f"[auto-production-batch:{batch_id}]",
            }
            await raw_service.create(payload, actor=actor)

            # стоимость по moving-average
            avg_price, cur = await self._compute_ingredient_avg_price(
                organization_id=organization_id,
                ingredient_id=str(ing["ingredient_id"]),
            )
            line_cost = (avg_price * consumed_qty).quantize(Decimal("0.01"))
            total_cost += line_cost
            if currency_id is None and cur is not None:
                currency_id = cur

        return total_cost.quantize(Decimal("0.01")), currency_id

    async def _persist_cost(
        self,
        *,
        batch_id: str,
        total_cost: Decimal,
        unit_cost: Decimal,
        currency_id: str | None,
    ) -> None:
        await self.repository.db.execute(
            """
            UPDATE feed_production_batches
            SET total_cost = $2,
                unit_cost = $3,
                cost_currency_id = $4,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            batch_id,
            str(total_cost),
            str(unit_cost),
            currency_id,
        )

    # ------------------ hooks ------------------

    async def _before_create(
        self, data: dict[str, Any], *, actor=None
    ) -> dict[str, Any]:
        out = dict(data)
        formula_id = str(out.get("formula_id") or "").strip()
        organization_id = str(out.get("organization_id") or "").strip()
        if not organization_id and actor is not None:
            organization_id = actor.organization_id
            out["organization_id"] = organization_id
        department_id = str(out.get("department_id") or "").strip()
        warehouse_id = out.get("warehouse_id") or None
        planned_output = _as_decimal(out.get("planned_output"))
        started_on = out.get("started_on")
        finished_on = out.get("finished_on")
        occurred_on = _as_date(finished_on or started_on or date.today())

        if formula_id and organization_id and department_id and planned_output > 0:
            await self._check_availability(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=(str(warehouse_id) if warehouse_id else None),
                formula_id=formula_id,
                required_output=planned_output,
                occurred_on=occurred_on,
            )
        return out

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        out = dict(data)
        merged = {**existing, **out}
        formula_id = str(merged.get("formula_id") or "").strip()
        organization_id = str(merged.get("organization_id") or "").strip()
        department_id = str(merged.get("department_id") or "").strip()
        warehouse_id = merged.get("warehouse_id") or None
        actual_output = _as_decimal(merged.get("actual_output"))
        planned_output = _as_decimal(merged.get("planned_output"))
        required = actual_output if actual_output > 0 else planned_output
        occurred_on = _as_date(
            merged.get("finished_on") or merged.get("started_on") or date.today()
        )

        if formula_id and organization_id and department_id and required > 0:
            await self._check_availability(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=(str(warehouse_id) if warehouse_id else None),
                formula_id=formula_id,
                required_output=required,
                occurred_on=occurred_on,
                exclude_batch_id=str(entity_id),
            )
        return out

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("actual_output"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=_feed_product_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity.get("finished_on") or entity.get("started_on")),
                    reference_table="feed_production_batches",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
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
        # 1. Incoming готового корма на склад.
        await self._sync_stock(entity)
        # 2. Списать сырьё по формуле + посчитать себестоимость.
        total_cost, currency_id = await self._rebuild_raw_consumptions(
            entity, actor=actor
        )
        actual_output = _as_decimal(entity.get("actual_output"))
        unit_cost = (
            (total_cost / actual_output).quantize(Decimal("0.0001"))
            if actual_output > 0
            else Decimal("0.0000")
        )
        await self._persist_cost(
            batch_id=str(entity["id"]),
            total_cost=total_cost,
            unit_cost=unit_cost,
            currency_id=currency_id,
        )

    async def _after_update(
        self, *, before: Mapping[str, Any], after: Mapping[str, Any], actor=None
    ) -> None:
        await self._sync_stock(after)
        total_cost, currency_id = await self._rebuild_raw_consumptions(
            after, actor=actor
        )
        actual_output = _as_decimal(after.get("actual_output"))
        unit_cost = (
            (total_cost / actual_output).quantize(Decimal("0.0001"))
            if actual_output > 0
            else Decimal("0.0000")
        )
        await self._persist_cost(
            batch_id=str(after["id"]),
            total_cost=total_cost,
            unit_cost=unit_cost,
            currency_id=currency_id,
        )

    async def _after_delete(
        self, *, deleted_entity: Mapping[str, Any], actor=None
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="feed_production_batches",
            reference_id=str(deleted_entity["id"]),
        )
        # feed_raw_consumptions уйдут каскадом через FK? Нет —
        # production_batch_id RESTRICT. Значит их надо удалить руками
        # ПЕРЕД удалением самого batch'а. Здесь мы уже после delete,
        # поэтому чистим "хвосты" напрямую в БД.
        await self.repository.db.execute(
            "DELETE FROM stock_movements "
            "WHERE reference_table = 'feed_raw_consumptions' "
            "  AND reference_id IN ("
            "    SELECT id FROM feed_raw_consumptions WHERE production_batch_id = $1"
            "  )",
            str(deleted_entity["id"]),
        )
        await self.repository.db.execute(
            "DELETE FROM feed_raw_consumptions WHERE production_batch_id = $1",
            str(deleted_entity["id"]),
        )

    async def delete(self, entity_id: Any, *, actor=None):
        # Удаляем зависимые расходы сырья перед удалением batch'а
        # (FK на production_batch_id = RESTRICT).
        raw_repo = FeedRawConsumptionRepository(self.repository.db)
        raw_service = FeedRawConsumptionService(raw_repo)
        existing = await self.repository.db.fetch(
            "SELECT id FROM feed_raw_consumptions WHERE production_batch_id = $1",
            str(entity_id),
        )
        for row in existing:
            await raw_service.delete(str(row["id"]), actor=actor)
        return await super().delete(entity_id, actor=actor)


class FeedRawArrivalService(CreatedByActorMixin, BaseService):
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
                    item_type="feed_raw",
                    item_key=_feed_raw_key(str(entity["ingredient_id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["arrived_on"]),
                    reference_table="feed_raw_arrivals",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=None,
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


class FeedConsumptionService(CreatedByActorMixin, BaseService):
    """Feed consumed by broilers — factory-side view of feed_consumptions.

    Rows linked to factory_daily_logs are written by
    FactoryDailyLogService (which already emits the stock movement with
    reference_table='factory_daily_logs'). Manually-created rows (without
    daily_log_id) emit their own outgoing feed movement here.
    """

    read_schema = FeedConsumptionReadSchema

    def __init__(self, repository: FeedConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _check_feed_balance(
        self,
        *,
        organization_id: str,
        department_id: str,
        warehouse_id: str | None,
        feed_type_id: str | None,
        production_batch_id: str | None,
        needed: Decimal,
        occurred_on: date,
        exclude_consumption_id: str | None = None,
    ) -> None:
        if needed <= 0:
            return
        if production_batch_id:
            item_key = _feed_product_key(production_batch_id)
        elif feed_type_id:
            item_key = _feed_product_key_by_type(feed_type_id)
        else:
            return
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        balance = await ledger.get_balance(
            organization_id=organization_id,
            department_id=department_id,
            warehouse_id=warehouse_id,
            item_type="feed",
            item_key=item_key,
            as_of=occurred_on,
        )
        if exclude_consumption_id is not None:
            own = await self.repository.db.fetchrow(
                """
                SELECT COALESCE(SUM(quantity), 0) AS q
                FROM stock_movements
                WHERE reference_table = 'feed_consumptions'
                  AND reference_id = $1
                  AND movement_kind = 'outgoing'
                """,
                exclude_consumption_id,
            )
            if own is not None:
                balance = balance + Decimal(str(own["q"] or 0))
        if balance < needed:
            raise ValidationError(
                f"Недостаточно корма: нужно {needed}, на складе {balance}"
            )

    async def _before_create(
        self, data: dict[str, Any], *, actor=None
    ) -> dict[str, Any]:
        # Rows owned by a daily log already checked by FactoryDailyLogService.
        if data.get("daily_log_id"):
            return data
        out = dict(data)
        quantity = _as_decimal(out.get("quantity"))
        organization_id = str(out.get("organization_id") or "").strip()
        if not organization_id and actor is not None:
            organization_id = actor.organization_id
        department_id = str(out.get("department_id") or "").strip()
        warehouse_id = (
            str(out["warehouse_id"]) if out.get("warehouse_id") else None
        )
        feed_type_id = out.get("feed_type_id")
        production_batch_id = out.get("production_batch_id")
        occurred_on = _as_date(out.get("consumed_on") or date.today())
        if organization_id and department_id and quantity > 0:
            await self._check_feed_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                feed_type_id=str(feed_type_id) if feed_type_id else None,
                production_batch_id=(
                    str(production_batch_id) if production_batch_id else None
                ),
                needed=quantity,
                occurred_on=occurred_on,
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
        if existing.get("daily_log_id") or data.get("daily_log_id"):
            return data
        out = dict(data)
        merged = {**existing, **out}
        quantity = _as_decimal(merged.get("quantity"))
        organization_id = str(merged.get("organization_id") or "")
        department_id = str(merged.get("department_id") or "")
        warehouse_id = (
            str(merged["warehouse_id"]) if merged.get("warehouse_id") else None
        )
        feed_type_id = merged.get("feed_type_id")
        production_batch_id = merged.get("production_batch_id")
        occurred_on = _as_date(merged.get("consumed_on") or date.today())
        if organization_id and department_id and quantity > 0:
            await self._check_feed_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                feed_type_id=str(feed_type_id) if feed_type_id else None,
                production_batch_id=(
                    str(production_batch_id) if production_batch_id else None
                ),
                needed=quantity,
                occurred_on=occurred_on,
                exclude_consumption_id=str(entity_id),
            )
        return out

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        # Skip when the daily log owns this row — daily-log service already
        # emitted the outgoing movement to avoid double-counting.
        if entity.get("daily_log_id"):
            ledger = StockLedgerService(StockMovementRepository(self.repository.db))
            await ledger.clear_reference_movements(
                reference_table="feed_consumptions",
                reference_id=str(entity["id"]),
            )
            return

        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            batch_id = entity.get("production_batch_id")
            if batch_id:
                item_key = _feed_product_key(str(batch_id))
            else:
                item_key = _feed_product_key_by_type(str(entity["feed_type_id"]))
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=item_key,
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="feed_consumptions",
                    reference_id=str(entity["id"]),
                    note=str(entity.get("note") or "") or None,
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


class FeedRawConsumptionService(CreatedByActorMixin, BaseService):
    read_schema = FeedRawConsumptionReadSchema

    def __init__(self, repository: FeedRawConsumptionRepository) -> None:
        super().__init__(repository=repository)

    async def _check_raw_balance(
        self,
        *,
        organization_id: str,
        department_id: str,
        warehouse_id: str | None,
        ingredient_id: str,
        needed: Decimal,
        occurred_on: date,
        exclude_consumption_id: str | None = None,
    ) -> None:
        if needed <= 0:
            return
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        balance = await ledger.get_balance(
            organization_id=organization_id,
            department_id=department_id,
            warehouse_id=warehouse_id,
            item_type="feed_raw",
            item_key=_feed_raw_key(ingredient_id),
            as_of=occurred_on,
        )
        if exclude_consumption_id is not None:
            own = await self.repository.db.fetchrow(
                """
                SELECT COALESCE(SUM(quantity), 0) AS q
                FROM stock_movements
                WHERE reference_table = 'feed_raw_consumptions'
                  AND reference_id = $1
                  AND movement_kind = 'outgoing'
                """,
                exclude_consumption_id,
            )
            if own is not None:
                balance = balance + Decimal(str(own["q"] or 0))
        if balance < needed:
            raise ValidationError(
                f"Недостаточно сырья: нужно {needed}, на складе {balance}"
            )

    async def _before_create(
        self, data: dict[str, Any], *, actor=None
    ) -> dict[str, Any]:
        # Если запись создаёт FeedProductionBatchService — он уже
        # сам провёл проверку суммарного наличия по всем ингредиентам.
        # Но на случай прямого ручного ввода оператора дублируем check.
        out = dict(data)
        quantity = _as_decimal(out.get("quantity"))
        organization_id = str(out.get("organization_id") or "").strip()
        if not organization_id and actor is not None:
            organization_id = actor.organization_id
        department_id = str(out.get("department_id") or "").strip()
        warehouse_id = (
            str(out["warehouse_id"]) if out.get("warehouse_id") else None
        )
        ingredient_id = str(out.get("ingredient_id") or "").strip()
        occurred_on = _as_date(out.get("consumed_on") or date.today())
        if organization_id and department_id and ingredient_id and quantity > 0:
            await self._check_raw_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                ingredient_id=ingredient_id,
                needed=quantity,
                occurred_on=occurred_on,
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
        quantity = _as_decimal(merged.get("quantity"))
        organization_id = str(merged.get("organization_id") or "")
        department_id = str(merged.get("department_id") or "")
        warehouse_id = (
            str(merged["warehouse_id"]) if merged.get("warehouse_id") else None
        )
        ingredient_id = str(merged.get("ingredient_id") or "")
        occurred_on = _as_date(merged.get("consumed_on") or date.today())
        if organization_id and department_id and ingredient_id and quantity > 0:
            await self._check_raw_balance(
                organization_id=organization_id,
                department_id=department_id,
                warehouse_id=warehouse_id,
                ingredient_id=ingredient_id,
                needed=quantity,
                occurred_on=occurred_on,
                exclude_consumption_id=str(entity_id),
            )
        return out

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = _as_decimal(entity.get("quantity"))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed_raw",
                    item_key=_feed_raw_key(str(entity["ingredient_id"])),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["consumed_on"]),
                    reference_table="feed_raw_consumptions",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
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


class FeedProductShipmentService(CreatedByActorMixin, BaseService):
    read_schema = FeedProductShipmentReadSchema

    def __init__(self, repository: FeedProductShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _ensure_quality_passed(self, production_batch_id: str) -> None:
        qc_repo = FeedProductionQualityCheckRepository(self.repository.db)
        latest = await qc_repo.get_optional_by(
            filters={"production_batch_id": production_batch_id},
            order_by=("checked_on desc", "created_at desc"),
        )
        if latest is None:
            raise ValidationError(
                "Shipment blocked: production batch has no quality check yet",
            )
        status = str(latest.get("status") or "").strip().lower()
        if status != "passed":
            raise ValidationError(
                f"Shipment blocked: latest quality check status is '{status}' (must be 'passed')",
            )

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        out = dict(data)
        production_batch_id = out.get("production_batch_id")
        if production_batch_id:
            await self._ensure_quality_passed(str(production_batch_id))
        return out

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        out = dict(data)
        production_batch_id = out.get("production_batch_id") or existing.get("production_batch_id")
        if production_batch_id and (
            "production_batch_id" in out or "quantity" in out
        ):
            await self._ensure_quality_passed(str(production_batch_id))
        return out

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        """Пишем outgoing только после подтверждения получения.

        Пока отгрузка в статусе 'sent' и клиент её не подтвердил
        (``acknowledged_at IS NULL``), корм числится на складе
        отправителя — это корректное поведение: товар физически едет,
        но юридически ещё не передан. Как только
        ``FeedProductShipmentAcknowledgementService`` ставит
        ``status='received'`` + ``acknowledged_at=now()``, ``_sync_stock``
        вызывается через ``_after_update`` и создаёт реальный outgoing.
        """
        quantity = _as_decimal(entity.get("quantity"))
        status = str(entity.get("status") or "").strip().lower()
        acknowledged_at = entity.get("acknowledged_at")
        is_confirmed = status == "received" or bool(acknowledged_at)
        movements: list[StockMovementDraft] = []
        if quantity > 0 and is_confirmed:
            production_batch_id = entity.get("production_batch_id")
            if production_batch_id:
                item_key = _feed_product_key(str(production_batch_id))
            else:
                item_key = _feed_product_key_by_type(str(entity["feed_type_id"]))
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="feed",
                    item_key=item_key,
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "kg"),
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="feed_product_shipments",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            )

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="feed_product_shipments",
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

        from app.services.units import resolve_measurement_unit_id
        unit_code = str(entity.get("unit") or "kg")
        measurement_unit_id = await resolve_measurement_unit_id(
            self.repository.db, str(entity["organization_id"]), unit_code,
        )
        payload: dict[str, Any] = {
            "organization_id": str(entity["organization_id"]),
            "department_id": str(entity["department_id"]),
            "client_id": str(entity["client_id"]),
            "item_type": "feed",
            "item_key": f"feed_shipment:{shipment_id}",
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
            reference_table="feed_product_shipments",
            reference_id=str(deleted_entity["id"]),
        )
        await self._delete_auto_ar(str(deleted_entity["id"]))


class FeedProductionQualityCheckService(BaseService):
    read_schema = FeedProductionQualityCheckReadSchema

    def __init__(self, repository: FeedProductionQualityCheckRepository) -> None:
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

        production_batch_id_raw = merged.get("production_batch_id")
        if not production_batch_id_raw:
            raise ValidationError("production_batch_id is required")
        production_batch_id = str(production_batch_id_raw)

        batch_repo = FeedProductionBatchRepository(self.repository.db)
        batch = await batch_repo.get_by_id_optional(production_batch_id)
        if batch is None:
            raise ValidationError("production_batch_id not found")

        organization_id = str(merged.get("organization_id") or batch.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(batch.get("organization_id")) != organization_id:
            raise AccessDeniedError("production batch belongs to another organization")

        department_id = merged.get("department_id")
        if not department_id:
            department_id = batch.get("department_id")
            if department_id is None:
                raise ValidationError("department_id is required")
            out["department_id"] = str(department_id)
        elif str(department_id) != str(batch.get("department_id")):
            raise ValidationError("department_id must match production batch department")

        out["production_batch_id"] = production_batch_id

        status_raw = merged.get("status")
        status = (str(status_raw).strip().lower() if status_raw else "pending") or "pending"
        if status not in FEED_QUALITY_CHECK_STATUSES:
            raise ValidationError(
                f"status must be one of: {', '.join(FEED_QUALITY_CHECK_STATUSES)}",
            )
        out["status"] = status

        grade_raw = merged.get("grade")
        if grade_raw:
            grade = str(grade_raw).strip().lower()
            if grade not in FEED_QUALITY_CHECK_GRADES:
                raise ValidationError(
                    f"grade must be one of: {', '.join(FEED_QUALITY_CHECK_GRADES)}",
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
        if "production_batch_id" in data and str(data["production_batch_id"]) != str(existing.get("production_batch_id")):
            raise ValidationError("production_batch_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)


__all__ = [
    "FeedTypeService",
    "FeedIngredientService",
    "FeedFormulaService",
    "FeedFormulaIngredientService",
    "FeedProductionBatchService",
    "FeedProductShipmentService",
    "FeedRawArrivalService",
    "FeedRawConsumptionService",
    "FeedProductionQualityCheckService",
]
