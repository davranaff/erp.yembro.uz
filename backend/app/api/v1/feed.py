from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.crud import build_crud_router
from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.db.pool import Database
from app.repositories.feed import (
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedLotShrinkageStateRepository,
    FeedProductionBatchRepository,
    FeedProductionQualityCheckRepository,
    FeedProductShipmentRepository,
    FeedRawArrivalRepository,
    FeedRawConsumptionRepository,
    FeedShrinkageProfileRepository,
    FeedTypeRepository,
)
from app.services.feed import (
    FeedFormulaService,
    FeedIngredientService,
    FeedProductShipmentService,
    FeedProductionBatchService,
    FeedProductionQualityCheckService,
    FeedRawArrivalService,
    FeedRawConsumptionService,
    FeedTypeService,
)
from app.services.feed_shrinkage import (
    FeedLotShrinkageStateService,
    FeedShrinkageProfileService,
    FeedShrinkageRunner,
    LOT_TYPES,
    ShrinkageApplyOutcome,
)


router = APIRouter(prefix="/feed", tags=["feed"])

router.include_router(
    build_crud_router(
        prefix="types",
        service_factory=lambda db: FeedTypeService(FeedTypeRepository(db)),
        permission_prefix="feed_type",
        tags=["feed-type"],
    )
)

router.include_router(
    build_crud_router(
        prefix="ingredients",
        service_factory=lambda db: FeedIngredientService(FeedIngredientRepository(db)),
        permission_prefix="feed_ingredient",
        tags=["feed-ingredient"],
    )
)

router.include_router(
    build_crud_router(
        prefix="formulas",
        service_factory=lambda db: FeedFormulaService(FeedFormulaRepository(db)),
        permission_prefix="feed_formula",
        tags=["feed-formula"],
    )
)

router.include_router(
    build_crud_router(
        prefix="raw-arrivals",
        service_factory=lambda db: FeedRawArrivalService(FeedRawArrivalRepository(db)),
        permission_prefix="feed_raw_arrival",
        tags=["feed-raw-arrival"],
    )
)

router.include_router(
    build_crud_router(
        prefix="raw-consumptions",
        service_factory=lambda db: FeedRawConsumptionService(FeedRawConsumptionRepository(db)),
        permission_prefix="feed_raw_consumption",
        tags=["feed-raw-consumption"],
    )
)

router.include_router(
    build_crud_router(
        prefix="production-batches",
        service_factory=lambda db: FeedProductionBatchService(FeedProductionBatchRepository(db)),
        permission_prefix="feed_production_batch",
        tags=["feed-production-batch"],
    )
)

router.include_router(
    build_crud_router(
        prefix="quality-checks",
        service_factory=lambda db: FeedProductionQualityCheckService(
            FeedProductionQualityCheckRepository(db)
        ),
        permission_prefix="feed_production_quality_check",
        tags=["feed-production-quality-check"],
    )
)

router.include_router(
    build_crud_router(
        prefix="product-shipments",
        service_factory=lambda db: FeedProductShipmentService(FeedProductShipmentRepository(db)),
        permission_prefix="feed_product_shipment",
        tags=["feed-product-shipment"],
    )
)

router.include_router(
    build_crud_router(
        prefix="shrinkage-profiles",
        service_factory=lambda db: FeedShrinkageProfileService(
            FeedShrinkageProfileRepository(db)
        ),
        permission_prefix="feed_shrinkage_profile",
        tags=["feed-shrinkage-profile"],
    )
)

router.include_router(
    build_crud_router(
        prefix="shrinkage-state",
        service_factory=lambda db: FeedLotShrinkageStateService(
            FeedLotShrinkageStateRepository(db)
        ),
        permission_prefix="feed_shrinkage_run",
        tags=["feed-shrinkage-state"],
    )
)


shrinkage_run_read = require_access("feed_shrinkage_run.read", roles=("admin", "manager"))
shrinkage_run_execute = require_access(
    "feed_shrinkage_run.execute", roles=("admin", "manager")
)


def _outcome_to_dict(outcome: ShrinkageApplyOutcome) -> dict[str, object]:
    return {
        "state_id": outcome.state_id,
        "lot_type": outcome.lot_type,
        "lot_id": outcome.lot_id,
        "profile_id": outcome.profile_id,
        "applied_on": outcome.applied_on.isoformat(),
        "loss_quantity": str(outcome.loss_quantity),
        "accumulated_loss": str(outcome.accumulated_loss),
        "initial_quantity": str(outcome.initial_quantity),
        "is_frozen": outcome.is_frozen,
        "periods_applied": outcome.periods_applied,
    }


class ShrinkageApplyRequest(BaseModel):
    on_date: date | None = Field(
        default=None,
        description="Дата, на которую прогнать расчёт. По умолчанию сегодня.",
    )
    lot_type: str | None = Field(
        default=None,
        description="Если задано вместе с lot_id — применяется только к одной партии.",
    )
    lot_id: str | None = None


@router.post(
    "/shrinkage-state/apply",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(shrinkage_run_execute)],
    tags=["feed-shrinkage-state"],
)
async def apply_shrinkage(
    payload: ShrinkageApplyRequest,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, object]:
    runner = FeedShrinkageRunner(db)
    on_date = payload.on_date or date.today()

    if payload.lot_id:
        if not payload.lot_type or payload.lot_type not in LOT_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="lot_type must be 'raw_arrival' or 'production_batch' when lot_id is provided",
            )
        outcome = await runner.apply_for_lot(
            lot_type=payload.lot_type,
            lot_id=payload.lot_id,
            on_date=on_date,
        )
        return {
            "applied_on": on_date.isoformat(),
            "outcomes": [_outcome_to_dict(outcome)] if outcome is not None else [],
        }

    outcomes = await runner.apply_for_organization(
        current_actor.organization_id, on_date=on_date
    )
    return {
        "applied_on": on_date.isoformat(),
        "outcomes": [_outcome_to_dict(o) for o in outcomes],
    }


@router.post(
    "/shrinkage-state/reset-lot/{state_id}",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(shrinkage_run_execute)],
    tags=["feed-shrinkage-state"],
)
async def reset_lot_shrinkage(
    state_id: str,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, object]:
    # Org-scope guard: the runner mutates a specific state row, and
    # users can only reset lots inside their own organization.
    state_repo = FeedLotShrinkageStateRepository(db)
    state = await state_repo.get_by_id_optional(state_id)
    if state is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="shrinkage state not found",
        )
    if (
        "admin" not in current_actor.roles
        and "super_admin" not in current_actor.roles
        and str(state["organization_id"]) != current_actor.organization_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-organization access denied",
        )

    runner = FeedShrinkageRunner(db)
    outcome = await runner.reset_lot(state_id)
    return {
        "state_id": state_id,
        "outcome": _outcome_to_dict(outcome) if outcome is not None else None,
    }


@router.get(
    "/shrinkage-state/report",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(shrinkage_run_read)],
    tags=["feed-shrinkage-state"],
)
async def shrinkage_report(
    date_from: date = Query(..., description="Начало периода (включительно)"),
    date_to: date = Query(..., description="Конец периода (включительно)"),
    warehouse_id: str | None = Query(default=None),
    item_type: str | None = Query(
        default=None,
        description="Фильтр по типу позиции: feed | feed_raw",
    ),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, object]:
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be >= date_from",
        )

    params: list[object] = [current_actor.organization_id, date_from, date_to]
    clauses = [
        "sm.organization_id = $1",
        "sm.movement_kind = 'shrinkage'",
        "sm.occurred_on BETWEEN $2 AND $3",
    ]
    cursor = 4
    if warehouse_id:
        clauses.append(f"sm.warehouse_id = ${cursor}")
        params.append(warehouse_id)
        cursor += 1
    if item_type:
        if item_type not in ("feed", "feed_raw"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="item_type must be 'feed' or 'feed_raw'",
            )
        clauses.append(f"sm.item_type = ${cursor}")
        params.append(item_type)
        cursor += 1

    rows = await db.fetch(
        f"""
        SELECT
            sm.item_type,
            sm.item_key,
            SUM(sm.quantity) AS total_loss,
            COUNT(*)         AS entries
        FROM stock_movements sm
        WHERE {' AND '.join(clauses)}
        GROUP BY sm.item_type, sm.item_key
        ORDER BY total_loss DESC
        """,
        *params,
    )
    return {
        "date_from": date_from.isoformat(),
        "date_to": date_to.isoformat(),
        "items": [
            {
                "item_type": row["item_type"],
                "item_key": row["item_key"],
                "total_loss": str(row["total_loss"]),
                "entries": int(row["entries"]),
            }
            for row in rows
        ],
    }


@router.get(
    "/shrinkage/overview",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(shrinkage_run_read)],
    tags=["feed-shrinkage-overview"],
)
async def shrinkage_overview(
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, object]:
    """Auto-applied, flat view of shrinkage per lot.

    Page users just want: «партия N — было 11 000 кг, сейчас 9 500 кг».
    This endpoint:

    1. Runs the shrinkage algorithm for today (idempotent —
       last_applied_on prevents double-counting, so every page view
       is at most one full cycle, usually zero).
    2. Returns a flat list of every lot that has an active profile,
       split into raw ingredients and finished feed.
    """
    runner = FeedShrinkageRunner(db)
    await runner.apply_for_organization(current_actor.organization_id)

    raw_rows = await db.fetch(
        """
        SELECT
            s.id::text              AS state_id,
            ra.id::text             AS lot_id,
            ra.arrived_on           AS started_on,
            fi.name                 AS name,
            fi.code                 AS code,
            w.name                  AS warehouse_name,
            s.initial_quantity      AS initial_quantity,
            s.accumulated_loss      AS accumulated_loss,
            s.last_applied_on       AS last_applied_on,
            s.is_frozen             AS is_frozen
        FROM feed_raw_arrivals ra
        LEFT JOIN feed_lot_shrinkage_state s
          ON s.lot_type = 'raw_arrival' AND s.lot_id = ra.id
        LEFT JOIN feed_ingredients fi ON fi.id = ra.ingredient_id
        LEFT JOIN warehouses w ON w.id = ra.warehouse_id
        WHERE ra.organization_id = $1 AND s.id IS NOT NULL
        ORDER BY ra.arrived_on DESC, ra.id
        """,
        current_actor.organization_id,
    )

    batch_rows = await db.fetch(
        """
        SELECT
            s.id::text              AS state_id,
            pb.id::text             AS lot_id,
            pb.finished_on          AS started_on,
            pb.batch_code           AS batch_code,
            ft.name                 AS name,
            ft.code                 AS code,
            w.name                  AS warehouse_name,
            s.initial_quantity      AS initial_quantity,
            s.accumulated_loss      AS accumulated_loss,
            s.last_applied_on       AS last_applied_on,
            s.is_frozen             AS is_frozen
        FROM feed_production_batches pb
        JOIN feed_formulas ff ON ff.id = pb.formula_id
        LEFT JOIN feed_types ft ON ft.id = ff.feed_type_id
        LEFT JOIN feed_lot_shrinkage_state s
          ON s.lot_type = 'production_batch' AND s.lot_id = pb.id
        LEFT JOIN warehouses w ON w.id = pb.warehouse_id
        WHERE pb.organization_id = $1 AND s.id IS NOT NULL
        ORDER BY pb.finished_on DESC NULLS LAST, pb.id
        """,
        current_actor.organization_id,
    )

    def _to_item(row: dict[str, object], *, lot_label_parts: list[str]) -> dict[str, object]:
        from decimal import Decimal as _D

        initial = _D(str(row["initial_quantity"] or 0))
        loss = _D(str(row["accumulated_loss"] or 0))
        current = initial - loss
        percent = (loss / initial * _D("100")) if initial > 0 else _D("0")
        return {
            "state_id": row["state_id"],
            "lot_id": row["lot_id"],
            "lot_label": " · ".join(p for p in lot_label_parts if p),
            "name": row["name"],
            "code": row["code"],
            "warehouse_name": row["warehouse_name"],
            "started_on": row["started_on"].isoformat() if row["started_on"] else None,
            "initial_quantity": str(initial),
            "current_quantity": str(current),
            "loss_quantity": str(loss),
            "loss_percent": f"{percent:.2f}",
            "last_applied_on": (
                row["last_applied_on"].isoformat() if row["last_applied_on"] else None
            ),
            "is_frozen": bool(row["is_frozen"]),
        }

    return {
        "ingredients": [
            _to_item(
                dict(row),
                lot_label_parts=[
                    str(row["name"] or ""),
                    (row["started_on"].isoformat() if row["started_on"] else ""),
                    str(row["warehouse_name"] or ""),
                ],
            )
            for row in raw_rows
        ],
        "feed_products": [
            _to_item(
                dict(row),
                lot_label_parts=[
                    str(row["name"] or ""),
                    str(row["batch_code"] or ""),
                    (row["started_on"].isoformat() if row["started_on"] else ""),
                ],
            )
            for row in batch_rows
        ],
    }


register_module_stats_route(
    router,
    module="feed",
    label="Feed",
    tables=(
        ModuleStatsTable(key="types", label="Types", table="feed_types"),
        ModuleStatsTable(key="ingredients", label="Ingredients", table="feed_ingredients"),
        ModuleStatsTable(key="formulas", label="Formulas", table="feed_formulas"),
        ModuleStatsTable(
            key="raw_arrivals",
            label="Raw Arrivals",
            table="feed_raw_arrivals",
        ),
        ModuleStatsTable(
            key="raw_consumptions",
            label="Raw Consumptions",
            table="feed_raw_consumptions",
        ),
        ModuleStatsTable(
            key="production_batches",
            label="Production Batches",
            table="feed_production_batches",
        ),
        ModuleStatsTable(
            key="quality_checks",
            label="Quality Checks",
            table="feed_production_quality_checks",
        ),
        ModuleStatsTable(
            key="product_shipments",
            label="Product Shipments",
            table="feed_product_shipments",
        ),
        ModuleStatsTable(
            key="shrinkage_profiles",
            label="Shrinkage Profiles",
            table="feed_shrinkage_profiles",
        ),
        ModuleStatsTable(
            key="shrinkage_state",
            label="Shrinkage State",
            table="feed_lot_shrinkage_state",
        ),
    ),
)

__all__ = ["router"]
