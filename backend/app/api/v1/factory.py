from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.factory import (
    FactoryDailyLogRepository,
    FactoryFlockRepository,
    FactoryMedicineUsageRepository,
    FactoryShipmentRepository,
    FactoryVaccinationPlanRepository,
)
from app.services.factory import (
    FactoryDailyLogService,
    FactoryFlockService,
    FactoryMedicineUsageService,
    FactoryShipmentService,
    FactoryVaccinationPlanService,
)


router = APIRouter(prefix="/factory", tags=["factory"])

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
