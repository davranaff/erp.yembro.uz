from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.egg import (
    EggProductionRepository,
    EggQualityCheckRepository,
    EggShipmentRepository,
)
from app.services.egg import (
    EggProductionService,
    EggQualityCheckService,
    EggShipmentService,
)


router = APIRouter(prefix="/egg", tags=["egg"])

router.include_router(
    build_crud_router(
        prefix="production",
        service_factory=lambda db: EggProductionService(EggProductionRepository(db)),
        permission_prefix="egg_production",
        tags=["egg-production"],
    )
)

router.include_router(
    build_crud_router(
        prefix="shipments",
        service_factory=lambda db: EggShipmentService(EggShipmentRepository(db)),
        permission_prefix="egg_shipment",
        tags=["egg-shipment"],
    )
)

router.include_router(
    build_crud_router(
        prefix="quality-checks",
        service_factory=lambda db: EggQualityCheckService(EggQualityCheckRepository(db)),
        permission_prefix="egg_quality_check",
        tags=["egg-quality-check"],
    )
)

register_module_stats_route(
    router,
    module="egg",
    label="Egg",
    tables=(
        ModuleStatsTable(key="production", label="Production", table="egg_production"),
        ModuleStatsTable(key="shipments", label="Shipments", table="egg_shipments"),
        ModuleStatsTable(key="quality_checks", label="Quality Checks", table="egg_quality_checks"),
    ),
)

__all__ = ["router"]
