from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Mapping
from uuid import UUID, uuid4

from app.core.exceptions import AccessDeniedError, ConflictError, NotFoundError, ValidationError
from app.db.pool import Database
from app.repositories.core import WarehouseRepository
from app.repositories.feed import (
    FeedIngredientRepository,
    FeedLotShrinkageStateRepository,
    FeedShrinkageProfileRepository,
    FeedTypeRepository,
)
from app.repositories.inventory import StockMovementRepository
from app.schemas.feed import (
    FeedLotShrinkageStateReadSchema,
    FeedShrinkageProfileReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


SHRINKAGE_REFERENCE_TABLE = "feed_lot_shrinkage_state"
SHRINKAGE_MOVEMENT_KIND = "shrinkage"
QUANTIZE = Decimal("0.001")
PERCENT_Q = Decimal("0.001")


TARGET_TYPES = ("ingredient", "feed_type")
LOT_TYPES = ("raw_arrival", "production_batch")


def _as_decimal(raw_value: object, default: str = "0") -> Decimal:
    if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
        return Decimal(default)
    if isinstance(raw_value, Decimal):
        return raw_value
    return Decimal(str(raw_value))


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(QUANTIZE)


def _as_date(raw_value: object) -> date | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _feed_raw_key(ingredient_id: str) -> str:
    return f"feed_raw:{ingredient_id}"


def _feed_product_key(production_batch_id: str) -> str:
    return f"feed_product:{production_batch_id}"


@dataclass(slots=True)
class CompoundShrinkageResult:
    total_loss: Decimal
    periods_applied: int
    freeze_after: bool


def compute_compound_shrinkage(
    *,
    current_balance: Decimal,
    initial_quantity: Decimal,
    accumulated_loss: Decimal,
    percent_per_period: Decimal,
    max_total_percent: Decimal | None,
    full_periods: int,
) -> CompoundShrinkageResult:
    """Pure algorithm kernel.

    Applies ``percent_per_period`` of the current remaining balance
    ``full_periods`` times. If ``max_total_percent`` is set, the last
    delta is clipped to keep ``accumulated_loss + total_loss`` within
    ``initial_quantity * max_total_percent / 100`` and the state is
    marked for freezing. Also freezes when the balance reaches zero.
    """

    total_loss = Decimal("0")
    remaining = current_balance
    freeze_after = False
    periods_applied = 0

    if full_periods <= 0 or remaining <= 0:
        return CompoundShrinkageResult(total_loss, periods_applied, freeze_after)

    percent_factor = percent_per_period / Decimal("100")
    max_total_cap: Decimal | None = None
    if max_total_percent is not None:
        max_total_cap = (initial_quantity * max_total_percent) / Decimal("100")

    for _ in range(full_periods):
        if remaining <= 0:
            freeze_after = True
            break
        delta = (remaining * percent_factor).quantize(QUANTIZE)
        if delta <= 0:
            break

        if max_total_cap is not None:
            remaining_cap = (max_total_cap - accumulated_loss - total_loss).quantize(QUANTIZE)
            if remaining_cap <= 0:
                freeze_after = True
                break
            if delta > remaining_cap:
                delta = remaining_cap
                freeze_after = True

        if delta > remaining:
            delta = remaining.quantize(QUANTIZE)
            freeze_after = True

        total_loss += delta
        remaining -= delta
        periods_applied += 1
        if freeze_after:
            break

    return CompoundShrinkageResult(
        total_loss=total_loss.quantize(QUANTIZE),
        periods_applied=periods_applied,
        freeze_after=freeze_after,
    )


@dataclass(slots=True)
class ShrinkageApplyOutcome:
    state_id: str
    lot_type: str
    lot_id: str
    profile_id: str
    applied_on: date
    loss_quantity: Decimal
    accumulated_loss: Decimal
    initial_quantity: Decimal
    is_frozen: bool
    periods_applied: int


class FeedShrinkageProfileService(BaseService):
    """CRUD for shrinkage profiles.

    Validation:
      * ``target_type`` must be ``ingredient`` / ``feed_type`` and the
        matching FK column must be filled (the other NULL). The DB has a
        CHECK constraint for this, but failing at the service layer gives
        a friendlier error.
      * Referenced ingredient / feed_type / warehouse must belong to the
        same organization as the profile.
      * Numeric bounds (``period_days > 0``, percent in [0, 100]) are
        also enforced at the service layer for better error messages.
    """

    read_schema = FeedShrinkageProfileReadSchema

    def __init__(self, repository: FeedShrinkageProfileRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.append(
            {
                "name": "target_type",
                "reference": {
                    "table": "__static__",
                    "column": "value",
                    "label_column": "label",
                    "multiple": False,
                    "options": [
                        {"value": "ingredient", "label": "Сырьё (ингредиент)"},
                        {"value": "feed_type", "label": "Готовый корм (тип)"},
                    ],
                },
            }
        )
        return fields

    async def _resolve_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        target_type = str(merged.get("target_type") or "").strip().lower()
        if target_type not in TARGET_TYPES:
            raise ValidationError(
                "target_type must be 'ingredient' or 'feed_type'"
            )
        out["target_type"] = target_type

        organization_id = str(merged.get("organization_id") or "").strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        ingredient_id_raw = merged.get("ingredient_id")
        feed_type_id_raw = merged.get("feed_type_id")
        ingredient_id = str(ingredient_id_raw).strip() if ingredient_id_raw else None
        feed_type_id = str(feed_type_id_raw).strip() if feed_type_id_raw else None

        if target_type == "ingredient":
            if not ingredient_id:
                raise ValidationError("ingredient_id is required for ingredient target")
            if feed_type_id:
                raise ValidationError(
                    "feed_type_id must be empty when target_type='ingredient'"
                )
            ingredient = await FeedIngredientRepository(self.repository.db).get_by_id_optional(
                ingredient_id
            )
            if ingredient is None:
                raise ValidationError("ingredient_id not found")
            if str(ingredient["organization_id"]) != organization_id:
                raise AccessDeniedError("ingredient belongs to another organization")
            out["ingredient_id"] = ingredient_id
            out["feed_type_id"] = None
        else:  # feed_type
            if not feed_type_id:
                raise ValidationError("feed_type_id is required for feed_type target")
            if ingredient_id:
                raise ValidationError(
                    "ingredient_id must be empty when target_type='feed_type'"
                )
            feed_type = await FeedTypeRepository(self.repository.db).get_by_id_optional(
                feed_type_id
            )
            if feed_type is None:
                raise ValidationError("feed_type_id not found")
            if str(feed_type["organization_id"]) != organization_id:
                raise AccessDeniedError("feed_type belongs to another organization")
            out["feed_type_id"] = feed_type_id
            out["ingredient_id"] = None

        warehouse_id_raw = merged.get("warehouse_id")
        warehouse_id = str(warehouse_id_raw).strip() if warehouse_id_raw else None
        if warehouse_id:
            warehouse = await WarehouseRepository(self.repository.db).get_by_id_optional(warehouse_id)
            if warehouse is None:
                raise ValidationError("warehouse_id not found")
            if str(warehouse["organization_id"]) != organization_id:
                raise AccessDeniedError("warehouse belongs to another organization")
            out["warehouse_id"] = warehouse_id
        else:
            out["warehouse_id"] = None

        period_days = int(merged.get("period_days") or 0)
        if period_days <= 0:
            raise ValidationError("period_days must be positive")
        out["period_days"] = period_days

        percent_per_period = _as_decimal(merged.get("percent_per_period"))
        if percent_per_period < 0 or percent_per_period > 100:
            raise ValidationError("percent_per_period must be between 0 and 100")
        out["percent_per_period"] = percent_per_period.quantize(PERCENT_Q)

        max_total_raw = merged.get("max_total_percent")
        if max_total_raw is None or (isinstance(max_total_raw, str) and not max_total_raw.strip()):
            out["max_total_percent"] = None
        else:
            max_total = _as_decimal(max_total_raw)
            if max_total < 0 or max_total > 100:
                raise ValidationError("max_total_percent must be between 0 and 100")
            out["max_total_percent"] = max_total.quantize(PERCENT_Q)

        stop_after_raw = merged.get("stop_after_days")
        if stop_after_raw is None or (isinstance(stop_after_raw, str) and not str(stop_after_raw).strip()):
            out["stop_after_days"] = None
        else:
            stop_after = int(stop_after_raw)
            if stop_after <= 0:
                raise ValidationError("stop_after_days must be positive or null")
            out["stop_after_days"] = stop_after

        starts_after_raw = merged.get("starts_after_days")
        starts_after = int(starts_after_raw) if starts_after_raw is not None else 0
        if starts_after < 0:
            raise ValidationError("starts_after_days must be non-negative")
        out["starts_after_days"] = starts_after

        if "is_active" in data and data["is_active"] is not None:
            out["is_active"] = bool(data["is_active"])
        elif existing is None:
            out["is_active"] = bool(merged.get("is_active", True))

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
        if "organization_id" in data and str(data["organization_id"]) != str(
            existing.get("organization_id")
        ):
            raise ValidationError("organization_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)


class FeedLotShrinkageStateService(BaseService):
    """Read-only-ish CRUD over lot state.

    State rows are created and mutated by :class:`FeedShrinkageRunner`.
    Exposing a CRUD surface is still useful for listing / inspection and
    for the audit trail; manual writes from the UI should be blocked.
    """

    read_schema = FeedLotShrinkageStateReadSchema

    def __init__(self, repository: FeedLotShrinkageStateRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.append(
            {
                "name": "lot_type",
                "reference": {
                    "table": "__static__",
                    "column": "value",
                    "label_column": "label",
                    "multiple": False,
                    "options": [
                        {"value": "raw_arrival", "label": "Приход сырья"},
                        {"value": "production_batch", "label": "Производственная партия"},
                    ],
                },
            }
        )
        return fields

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        raise ValidationError(
            "Shrinkage state rows are created automatically by the "
            "shrinkage runner. Use POST /feed/shrinkage-state/apply "
            "to generate them."
        )

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing,
        actor=None,
    ) -> dict[str, Any]:
        # The only thing users may toggle manually is `is_frozen` — useful
        # when a lot is written off / returned and shrinkage must stop
        # earlier than the profile dictates.
        allowed_fields = {"is_frozen"}
        filtered = {k: v for k, v in data.items() if k in allowed_fields}
        if not filtered:
            raise ValidationError(
                "Only is_frozen can be edited manually on a shrinkage state row"
            )
        if "is_frozen" in filtered:
            filtered["is_frozen"] = bool(filtered["is_frozen"])
        return filtered


class FeedShrinkageRunner:
    """Applies shrinkage profiles to active feed lots.

    Used by:
      * nightly Taskiq cron (phase 2);
      * manual ``POST /feed/shrinkage-state/apply`` endpoint — admin-only,
        safe to call repeatedly thanks to ``last_applied_on`` idempotency;
      * ``POST /feed/shrinkage-state/reset-lot/{state_id}`` which first
        deletes existing shrinkage movements, zeroes the state row, and
        then replays the algorithm through :meth:`apply_for_lot`.
    """

    def __init__(self, db: Database) -> None:
        self.db = db
        self.profile_repo = FeedShrinkageProfileRepository(db)
        self.state_repo = FeedLotShrinkageStateRepository(db)
        self.movement_repo = StockMovementRepository(db)
        self.warehouse_repo = WarehouseRepository(db)
        self.ledger = StockLedgerService(self.movement_repo, self.warehouse_repo)

    # ---------- public API ----------

    async def apply_for_organization(
        self,
        organization_id: str,
        *,
        on_date: date | None = None,
    ) -> list[ShrinkageApplyOutcome]:
        run_on = on_date or date.today()
        outcomes: list[ShrinkageApplyOutcome] = []

        raw_lots = await self.db.fetch(
            """
            SELECT
                ra.id::text            AS lot_id,
                'raw_arrival'::text    AS lot_type,
                ra.organization_id::text AS organization_id,
                ra.department_id::text AS department_id,
                ra.warehouse_id::text  AS warehouse_id,
                ra.ingredient_id::text AS ingredient_id,
                NULL::text             AS feed_type_id,
                ra.arrived_on          AS started_on,
                ra.quantity            AS initial_quantity,
                ra.unit                AS unit
            FROM feed_raw_arrivals ra
            WHERE ra.organization_id = $1
              AND ra.quantity > 0
            """,
            organization_id,
        )
        for lot in raw_lots:
            outcome = await self._apply_for_lot_row(dict(lot), on_date=run_on)
            if outcome is not None:
                outcomes.append(outcome)

        batch_lots = await self.db.fetch(
            """
            SELECT
                pb.id::text              AS lot_id,
                'production_batch'::text AS lot_type,
                pb.organization_id::text AS organization_id,
                pb.department_id::text   AS department_id,
                pb.warehouse_id::text    AS warehouse_id,
                NULL::text               AS ingredient_id,
                ff.feed_type_id::text    AS feed_type_id,
                pb.finished_on           AS started_on,
                pb.actual_output         AS initial_quantity,
                pb.unit                  AS unit
            FROM feed_production_batches pb
            JOIN feed_formulas ff ON ff.id = pb.formula_id
            WHERE pb.organization_id = $1
              AND pb.actual_output > 0
              AND pb.finished_on IS NOT NULL
            """,
            organization_id,
        )
        for lot in batch_lots:
            outcome = await self._apply_for_lot_row(dict(lot), on_date=run_on)
            if outcome is not None:
                outcomes.append(outcome)

        return outcomes

    async def apply_for_lot(
        self,
        *,
        lot_type: str,
        lot_id: str,
        on_date: date | None = None,
    ) -> ShrinkageApplyOutcome | None:
        run_on = on_date or date.today()
        lot = await self._fetch_lot(lot_type=lot_type, lot_id=lot_id)
        if lot is None:
            raise NotFoundError("lot not found")
        return await self._apply_for_lot_row(lot, on_date=run_on)

    async def reset_lot(self, state_id: str) -> ShrinkageApplyOutcome | None:
        state = await self.state_repo.get_by_id_optional(state_id)
        if state is None:
            raise NotFoundError("shrinkage state not found")

        # Revert the current accumulated loss by deleting every shrinkage
        # stock_movement that references this state row. Balances
        # recompute automatically from the remaining ledger.
        await self.movement_repo.delete_by_reference(
            reference_table=SHRINKAGE_REFERENCE_TABLE,
            reference_id=str(state["id"]),
        )
        await self.state_repo.update_by_id(
            str(state["id"]),
            {
                "accumulated_loss": Decimal("0"),
                "last_applied_on": None,
                "is_frozen": False,
            },
        )

        lot = await self._fetch_lot(
            lot_type=str(state["lot_type"]),
            lot_id=str(state["lot_id"]),
        )
        if lot is None:
            # Lot was deleted out from under us — drop the state too.
            await self.state_repo.delete_by_id(str(state["id"]))
            return None

        return await self._apply_for_lot_row(lot, on_date=date.today())

    # ---------- internals ----------

    async def _fetch_lot(self, *, lot_type: str, lot_id: str) -> dict[str, Any] | None:
        if lot_type == "raw_arrival":
            row = await self.db.fetchrow(
                """
                SELECT
                    ra.id::text            AS lot_id,
                    'raw_arrival'::text    AS lot_type,
                    ra.organization_id::text AS organization_id,
                    ra.department_id::text AS department_id,
                    ra.warehouse_id::text  AS warehouse_id,
                    ra.ingredient_id::text AS ingredient_id,
                    NULL::text             AS feed_type_id,
                    ra.arrived_on          AS started_on,
                    ra.quantity            AS initial_quantity,
                    ra.unit                AS unit
                FROM feed_raw_arrivals ra
                WHERE ra.id = $1
                """,
                lot_id,
            )
            return dict(row) if row is not None else None
        if lot_type == "production_batch":
            row = await self.db.fetchrow(
                """
                SELECT
                    pb.id::text              AS lot_id,
                    'production_batch'::text AS lot_type,
                    pb.organization_id::text AS organization_id,
                    pb.department_id::text   AS department_id,
                    pb.warehouse_id::text    AS warehouse_id,
                    NULL::text               AS ingredient_id,
                    ff.feed_type_id::text    AS feed_type_id,
                    pb.finished_on           AS started_on,
                    pb.actual_output         AS initial_quantity,
                    pb.unit                  AS unit
                FROM feed_production_batches pb
                JOIN feed_formulas ff ON ff.id = pb.formula_id
                WHERE pb.id = $1
                """,
                lot_id,
            )
            return dict(row) if row is not None else None
        raise ValidationError(f"unknown lot_type: {lot_type}")

    async def _resolve_profile(
        self,
        *,
        organization_id: str,
        lot_type: str,
        ingredient_id: str | None,
        feed_type_id: str | None,
        warehouse_id: str | None,
    ) -> dict[str, Any] | None:
        """Pick the active profile. Warehouse-specific wins over global."""
        if lot_type == "raw_arrival":
            if not ingredient_id:
                return None
            row = await self.db.fetchrow(
                """
                SELECT *
                FROM feed_shrinkage_profiles
                WHERE organization_id = $1
                  AND target_type = 'ingredient'
                  AND ingredient_id = $2
                  AND is_active = TRUE
                  AND (warehouse_id = $3 OR warehouse_id IS NULL)
                ORDER BY (warehouse_id IS NULL) ASC
                LIMIT 1
                """,
                organization_id,
                ingredient_id,
                warehouse_id,
            )
            return dict(row) if row is not None else None

        if lot_type == "production_batch":
            if not feed_type_id:
                return None
            row = await self.db.fetchrow(
                """
                SELECT *
                FROM feed_shrinkage_profiles
                WHERE organization_id = $1
                  AND target_type = 'feed_type'
                  AND feed_type_id = $2
                  AND is_active = TRUE
                  AND (warehouse_id = $3 OR warehouse_id IS NULL)
                ORDER BY (warehouse_id IS NULL) ASC
                LIMIT 1
                """,
                organization_id,
                feed_type_id,
                warehouse_id,
            )
            return dict(row) if row is not None else None

        return None

    async def _get_or_create_state(
        self,
        *,
        lot: Mapping[str, Any],
        profile: Mapping[str, Any],
    ) -> dict[str, Any]:
        state = await self.state_repo.get_optional_by(
            filters={"lot_type": lot["lot_type"], "lot_id": lot["lot_id"]},
        )
        if state is not None:
            # Profile may have been swapped out (new profile became
            # active that better matches this lot). Keep the same
            # state row but point it at the current profile.
            if str(state.get("profile_id")) != str(profile["id"]):
                state = await self.state_repo.update_by_id(
                    str(state["id"]),
                    {"profile_id": str(profile["id"])},
                )
            return state

        created = await self.state_repo.create(
            {
                "id": str(uuid4()),
                "organization_id": str(lot["organization_id"]),
                "lot_type": str(lot["lot_type"]),
                "lot_id": str(lot["lot_id"]),
                "profile_id": str(profile["id"]),
                "initial_quantity": _as_decimal(lot["initial_quantity"]).quantize(QUANTIZE),
                "accumulated_loss": Decimal("0"),
                "last_applied_on": None,
                "is_frozen": False,
            }
        )
        return created

    async def _apply_for_lot_row(
        self,
        lot: dict[str, Any],
        *,
        on_date: date,
    ) -> ShrinkageApplyOutcome | None:
        started_on = _as_date(lot.get("started_on"))
        if started_on is None or on_date < started_on:
            return None

        profile = await self._resolve_profile(
            organization_id=str(lot["organization_id"]),
            lot_type=str(lot["lot_type"]),
            ingredient_id=str(lot["ingredient_id"]) if lot.get("ingredient_id") else None,
            feed_type_id=str(lot["feed_type_id"]) if lot.get("feed_type_id") else None,
            warehouse_id=str(lot["warehouse_id"]) if lot.get("warehouse_id") else None,
        )
        if profile is None:
            return None

        state = await self._get_or_create_state(lot=lot, profile=profile)
        if bool(state.get("is_frozen")):
            return None

        initial_quantity = _as_decimal(state["initial_quantity"])
        accumulated_loss = _as_decimal(state.get("accumulated_loss"))

        days_since_start = (on_date - started_on).days
        starts_after_days = int(profile.get("starts_after_days") or 0)
        if days_since_start < starts_after_days:
            return None

        stop_after_days = profile.get("stop_after_days")
        if stop_after_days is not None and days_since_start > int(stop_after_days):
            # Past the stop cutoff — freeze without doing any more work.
            await self.state_repo.update_by_id(
                str(state["id"]),
                {"is_frozen": True},
            )
            return None

        last_applied_on = _as_date(state.get("last_applied_on"))
        if last_applied_on is None:
            cycle_anchor = started_on + timedelta(days=starts_after_days)
        else:
            cycle_anchor = last_applied_on

        period_days = int(profile["period_days"])
        days_since_anchor = (on_date - cycle_anchor).days
        full_periods = days_since_anchor // period_days
        if full_periods <= 0:
            return None

        # Per-lot remaining. Stock ledger aggregates by item_key (not by
        # specific arrival / batch), so we cannot reliably subtract
        # consumption per-lot from the ledger. v1 uses
        # `initial_quantity − accumulated_loss` as the remaining-in-lot,
        # which the spec explicitly allows. The CHECK constraint on the
        # table also caps `accumulated_loss <= initial_quantity`, so this
        # keeps the algorithm and the schema consistent.
        lot_remaining = initial_quantity - accumulated_loss
        if lot_remaining <= 0:
            await self.state_repo.update_by_id(
                str(state["id"]),
                {"is_frozen": True, "last_applied_on": on_date},
            )
            return None
        current_balance = lot_remaining

        percent_per_period = _as_decimal(profile["percent_per_period"])
        max_total_percent_raw = profile.get("max_total_percent")
        max_total_percent = (
            _as_decimal(max_total_percent_raw) if max_total_percent_raw is not None else None
        )

        computation = compute_compound_shrinkage(
            current_balance=current_balance,
            initial_quantity=initial_quantity,
            accumulated_loss=accumulated_loss,
            percent_per_period=percent_per_period,
            max_total_percent=max_total_percent,
            full_periods=full_periods,
        )
        total_loss = computation.total_loss
        freeze_after = computation.freeze_after
        periods_applied = computation.periods_applied

        if total_loss <= 0:
            if freeze_after:
                await self.state_repo.update_by_id(
                    str(state["id"]),
                    {"is_frozen": True, "last_applied_on": on_date},
                )
            return None

        total_loss = total_loss.quantize(QUANTIZE)
        new_accumulated = (accumulated_loss + total_loss).quantize(QUANTIZE)
        await self._upsert_movement(
            state_id=str(state["id"]),
            lot=lot,
            total_accumulated_loss=new_accumulated,
            on_date=on_date,
            percent_per_period=percent_per_period,
        )

        updated_state = await self.state_repo.update_by_id(
            str(state["id"]),
            {
                "accumulated_loss": new_accumulated,
                "last_applied_on": on_date,
                "is_frozen": bool(freeze_after),
            },
        )

        return ShrinkageApplyOutcome(
            state_id=str(updated_state["id"]),
            lot_type=str(lot["lot_type"]),
            lot_id=str(lot["lot_id"]),
            profile_id=str(profile["id"]),
            applied_on=on_date,
            loss_quantity=total_loss,
            accumulated_loss=new_accumulated,
            initial_quantity=initial_quantity,
            is_frozen=bool(freeze_after),
            periods_applied=periods_applied,
        )

    async def _upsert_movement(
        self,
        *,
        state_id: str,
        lot: Mapping[str, Any],
        total_accumulated_loss: Decimal,
        on_date: date,
        percent_per_period: Decimal,
    ) -> None:
        """One stock_movement per state row.

        The ``uq_stock_movement_reference_kind_scope`` unique index only
        permits a single movement per (reference_table, reference_id,
        kind, warehouse, item_type, item_key) — so each shrinkage cycle
        updates the existing row with the new cumulative loss + latest
        occurred_on, instead of inserting a fresh line.
        """
        lot_type = str(lot["lot_type"])
        if lot_type == "raw_arrival":
            item_type = "feed_raw"
            item_key = _feed_raw_key(str(lot["ingredient_id"]))
        else:
            item_type = "feed"
            item_key = _feed_product_key(str(lot["lot_id"]))

        note = f"Усушка {percent_per_period.normalize()}% от партии {lot['lot_id']}"
        existing = await self.db.fetchrow(
            """
            SELECT id
            FROM stock_movements
            WHERE reference_table = $1
              AND reference_id = $2
              AND movement_kind = $3
            LIMIT 1
            """,
            SHRINKAGE_REFERENCE_TABLE,
            state_id,
            SHRINKAGE_MOVEMENT_KIND,
        )

        if existing is not None:
            await self.db.execute(
                """
                UPDATE stock_movements
                SET quantity = $1,
                    occurred_on = $2,
                    note = $3
                WHERE id = $4
                """,
                total_accumulated_loss,
                on_date,
                note,
                str(existing["id"]),
            )
            return

        draft = StockMovementDraft(
            organization_id=str(lot["organization_id"]),
            department_id=str(lot["department_id"]) if lot.get("department_id") else None,
            item_type=item_type,
            item_key=item_key,
            movement_kind=SHRINKAGE_MOVEMENT_KIND,
            quantity=total_accumulated_loss,
            unit=str(lot.get("unit") or "kg"),
            occurred_on=on_date,
            reference_table=SHRINKAGE_REFERENCE_TABLE,
            reference_id=state_id,
            warehouse_id=str(lot["warehouse_id"]) if lot.get("warehouse_id") else None,
            note=note,
        )
        await self.ledger.record_movement(draft, exclude_reference_check=True)


__all__ = [
    "FeedShrinkageProfileService",
    "FeedLotShrinkageStateService",
    "FeedShrinkageRunner",
    "ShrinkageApplyOutcome",
    "SHRINKAGE_MOVEMENT_KIND",
    "SHRINKAGE_REFERENCE_TABLE",
    "LOT_TYPES",
    "TARGET_TYPES",
]
