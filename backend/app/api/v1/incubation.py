from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.incubation import (
    ChickShipmentRepository,
    FactoryMonthlyAnalyticsRepository,
    IncubationBatchRepository,
    IncubationMonthlyAnalyticsRepository,
    IncubationRunRepository,
)
from app.services.incubation import (
    ChickShipmentService,
    FactoryMonthlyAnalyticsService,
    IncubationBatchService,
    IncubationMonthlyAnalyticsService,
    IncubationRunService,
)


router = APIRouter(prefix="/incubation", tags=["incubation"])

router.include_router(
    build_crud_router(
        prefix="chick-shipments",
        service_factory=lambda db: ChickShipmentService(ChickShipmentRepository(db)),
        permission_prefix="chick_shipment",
        tags=["chick-shipment"],
    )
)

router.include_router(
    build_crud_router(
        prefix="batches",
        service_factory=lambda db: IncubationBatchService(IncubationBatchRepository(db)),
        permission_prefix="incubation_batch",
        tags=["incubation-batch"],
    )
)

router.include_router(
    build_crud_router(
        prefix="runs",
        service_factory=lambda db: IncubationRunService(IncubationRunRepository(db)),
        permission_prefix="incubation_run",
        tags=["incubation-run"],
    )
)

router.include_router(
    build_crud_router(
        prefix="monthly-analytics",
        service_factory=lambda db: IncubationMonthlyAnalyticsService(IncubationMonthlyAnalyticsRepository(db)),
        permission_prefix="incubation_monthly_analytics",
        tags=["incubation-monthly-analytics"],
    )
)

router.include_router(
    build_crud_router(
        prefix="factory-monthly-analytics",
        service_factory=lambda db: FactoryMonthlyAnalyticsService(FactoryMonthlyAnalyticsRepository(db)),
        permission_prefix="factory_monthly_analytics",
        tags=["factory-monthly-analytics"],
    )
)

register_module_stats_route(
    router,
    module="incubation",
    label="Incubation",
    tables=(
        ModuleStatsTable(key="chick_shipments", label="Chick Shipments", table="chick_shipments"),
        ModuleStatsTable(key="batches", label="Batches", table="incubation_batches"),
        ModuleStatsTable(key="runs", label="Runs", table="incubation_runs"),
        ModuleStatsTable(
            key="monthly_analytics",
            label="Monthly Analytics",
            table="incubation_monthly_analytics",
        ),
        ModuleStatsTable(
            key="factory_monthly_analytics",
            label="Factory Monthly Analytics",
            table="factory_monthly_analytics",
        ),
    ),
)

__all__ = ["router"]
