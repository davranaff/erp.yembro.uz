from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.incubation import (
    ChickShipmentRepository,
    IncubationBatchRepository,
    IncubationRunRepository,
)
from app.services.incubation import (
    ChickShipmentService,
    IncubationBatchService,
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

register_module_stats_route(
    router,
    module="incubation",
    label="Incubation",
    tables=(
        ModuleStatsTable(key="chick_shipments", label="Chick Shipments", table="chick_shipments"),
        ModuleStatsTable(key="batches", label="Batches", table="incubation_batches"),
        ModuleStatsTable(key="runs", label="Runs", table="incubation_runs"),
    ),
)

__all__ = ["router"]
