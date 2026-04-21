from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.crud import build_crud_router
from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.db.pool import Database
from app.repositories.factory import (
    FactoryDailyLogRepository,
    FactoryFlockRepository,
    FactoryMedicineUsageRepository,
    FactoryShipmentRepository,
    FactoryVaccinationPlanRepository,
)
from app.repositories.feed import FeedConsumptionRepository
from app.services.factory import (
    FactoryDailyLogService,
    FactoryFlockService,
    FactoryMedicineUsageService,
    FactoryShipmentService,
    FactoryVaccinationPlanService,
)
from app.services.feed import FeedConsumptionService


router = APIRouter(prefix="/factory", tags=["factory"])


def _float(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


@router.get(
    "/flocks/{flock_id}/kpi",
    dependencies=[Depends(require_access("factory_flock.read"))],
)
async def get_flock_kpi(
    flock_id: str,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    flock = await db.fetchrow(
        """
        SELECT id, organization_id, initial_count, current_count, status, arrived_on
        FROM factory_flocks
        WHERE id = $1 AND organization_id = $2
        """,
        flock_id,
        current_actor.organization_id,
    )
    if flock is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flock not found")

    log_row = await db.fetchrow(
        """
        SELECT
            COALESCE(SUM(mortality_count), 0) AS mortality_total,
            COALESCE(SUM(feed_consumed_kg), 0) AS feed_kg_total,
            COALESCE(SUM(feed_cost), 0) AS feed_cost_total,
            (
                SELECT avg_weight_kg FROM factory_daily_logs
                WHERE flock_id = $1 AND avg_weight_kg IS NOT NULL
                ORDER BY log_date DESC LIMIT 1
            ) AS latest_avg_weight_kg,
            (
                SELECT log_date FROM factory_daily_logs
                WHERE flock_id = $1
                ORDER BY log_date DESC LIMIT 1
            ) AS last_log_date
        FROM factory_daily_logs
        WHERE flock_id = $1
        """,
        flock_id,
    )

    shipment_row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(birds_count), 0) AS birds_shipped
        FROM factory_shipments
        WHERE flock_id = $1
        """,
        flock_id,
    )

    medicine_row = await db.fetchrow(
        """
        SELECT COALESCE(SUM(mc.quantity * COALESCE(mb.unit_cost, 0)), 0) AS medicine_cost_total
        FROM medicine_consumptions AS mc
        LEFT JOIN medicine_batches AS mb ON mb.id = mc.batch_id
        WHERE mc.factory_flock_id = $1
        """,
        flock_id,
    )

    initial_count = int(flock["initial_count"] or 0)
    current_count = int(flock["current_count"] or 0)
    mortality_total = int(log_row["mortality_total"] or 0) if log_row else 0
    feed_kg_total = _float(log_row["feed_kg_total"] if log_row else 0)
    feed_cost_total = _float(log_row["feed_cost_total"] if log_row else 0)
    latest_avg_weight_kg = _float(log_row["latest_avg_weight_kg"] if log_row else 0)
    birds_shipped = int(shipment_row["birds_shipped"] or 0) if shipment_row else 0
    medicine_cost_total = _float(medicine_row["medicine_cost_total"] if medicine_row else 0)

    live_weight_total_kg = latest_avg_weight_kg * current_count
    fcr = _safe_ratio(feed_kg_total, live_weight_total_kg)
    mortality_pct = _safe_ratio(mortality_total, initial_count)
    total_cost = feed_cost_total + medicine_cost_total
    cost_per_chick_alive = _safe_ratio(total_cost, current_count)
    cost_per_chick_shipped = _safe_ratio(total_cost, birds_shipped)

    return {
        "flock_id": flock_id,
        "status": flock["status"],
        "arrived_on": flock["arrived_on"].isoformat() if flock["arrived_on"] else None,
        "last_log_date": (
            log_row["last_log_date"].isoformat()
            if log_row and log_row["last_log_date"]
            else None
        ),
        "initial_count": initial_count,
        "current_count": current_count,
        "mortality_total": mortality_total,
        "mortality_pct": mortality_pct,
        "birds_shipped": birds_shipped,
        "feed_kg_total": feed_kg_total,
        "feed_cost_total": feed_cost_total,
        "medicine_cost_total": medicine_cost_total,
        "total_cost": total_cost,
        "latest_avg_weight_kg": latest_avg_weight_kg,
        "live_weight_total_kg": live_weight_total_kg,
        "fcr": fcr,
        "cost_per_chick_alive": cost_per_chick_alive,
        "cost_per_chick_shipped": cost_per_chick_shipped,
    }

router.include_router(
    build_crud_router(
        prefix="flocks",
        service_factory=lambda db: FactoryFlockService(FactoryFlockRepository(db)),
        permission_prefix="factory_flock",
        tags=["factory-flock"],
    )
)

router.include_router(
    build_crud_router(
        prefix="daily-logs",
        service_factory=lambda db: FactoryDailyLogService(FactoryDailyLogRepository(db)),
        permission_prefix="factory_daily_log",
        tags=["factory-daily-log"],
    )
)

router.include_router(
    build_crud_router(
        prefix="shipments",
        service_factory=lambda db: FactoryShipmentService(FactoryShipmentRepository(db)),
        permission_prefix="factory_shipment",
        tags=["factory-shipment"],
    )
)

router.include_router(
    build_crud_router(
        prefix="medicine-usages",
        service_factory=lambda db: FactoryMedicineUsageService(FactoryMedicineUsageRepository(db)),
        permission_prefix="factory_medicine_usage",
        tags=["factory-medicine-usage"],
    )
)

router.include_router(
    build_crud_router(
        prefix="vaccination-plans",
        service_factory=lambda db: FactoryVaccinationPlanService(FactoryVaccinationPlanRepository(db)),
        permission_prefix="factory_vaccination_plan",
        tags=["factory-vaccination-plan"],
    )
)

router.include_router(
    build_crud_router(
        prefix="feed-consumptions",
        service_factory=lambda db: FeedConsumptionService(FeedConsumptionRepository(db)),
        permission_prefix="feed_consumption",
        tags=["factory-feed-consumption"],
    )
)

register_module_stats_route(
    router,
    module="factory",
    label="Factory",
    tables=(
        ModuleStatsTable(key="factory_flocks", label="Flocks", table="factory_flocks"),
        ModuleStatsTable(key="factory_daily_logs", label="Daily Logs", table="factory_daily_logs"),
        ModuleStatsTable(key="factory_shipments", label="Shipments", table="factory_shipments"),
        ModuleStatsTable(key="factory_medicine_usages", label="Medicine Usages", table="factory_medicine_usages"),
        ModuleStatsTable(key="factory_vaccination_plans", label="Vaccination Plans", table="factory_vaccination_plans"),
    ),
)

__all__ = ["router"]
