from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.slaughter import (
    SlaughterMonthlyAnalyticsRepository,
    SlaughterProcessingRepository,
    SlaughterQualityCheckRepository,
    SlaughterSemiProductRepository,
    SlaughterSemiProductShipmentRepository,
)
from app.services.slaughter import (
    SlaughterMonthlyAnalyticsService,
    SlaughterProcessingService,
    SlaughterQualityCheckService,
    SlaughterSemiProductShipmentService,
    SlaughterSemiProductService,
)


router = APIRouter(prefix="/slaughter", tags=["slaughter"])

router.include_router(
    build_crud_router(
        prefix="processings",
        service_factory=lambda db: SlaughterProcessingService(SlaughterProcessingRepository(db)),
        permission_prefix="slaughter_processing",
        tags=["slaughter-processing"],
    )
)

router.include_router(
    build_crud_router(
        prefix="semi-products",
        service_factory=lambda db: SlaughterSemiProductService(SlaughterSemiProductRepository(db)),
        permission_prefix="slaughter_semi_product",
        tags=["slaughter-semi-product"],
    )
)

router.include_router(
    build_crud_router(
        prefix="semi-product-shipments",
        service_factory=lambda db: SlaughterSemiProductShipmentService(
            SlaughterSemiProductShipmentRepository(db),
        ),
        permission_prefix="slaughter_semi_product_shipment",
        tags=["slaughter-semi-product-shipment"],
    )
)

router.include_router(
    build_crud_router(
        prefix="quality-checks",
        service_factory=lambda db: SlaughterQualityCheckService(
            SlaughterQualityCheckRepository(db),
        ),
        permission_prefix="slaughter_quality_check",
        tags=["slaughter-quality-check"],
    )
)

router.include_router(
    build_crud_router(
        prefix="monthly-analytics",
        service_factory=lambda db: SlaughterMonthlyAnalyticsService(
            SlaughterMonthlyAnalyticsRepository(db),
        ),
        permission_prefix="slaughter_monthly_analytics",
        tags=["slaughter-monthly-analytics"],
    )
)

register_module_stats_route(
    router,
    module="slaughter",
    label="Slaughter",
    tables=(
        ModuleStatsTable(key="processings", label="Processings", table="slaughter_processings"),
        ModuleStatsTable(key="semi_products", label="Semi Products", table="slaughter_semi_products"),
        ModuleStatsTable(
            key="semi_product_shipments",
            label="Semi Product Shipments",
            table="slaughter_semi_product_shipments",
        ),
        ModuleStatsTable(
            key="quality_checks",
            label="Quality Checks",
            table="slaughter_quality_checks",
        ),
        ModuleStatsTable(
            key="monthly_analytics",
            label="Monthly Analytics",
            table="slaughter_monthly_analytics",
        ),
    ),
)

__all__ = ["router"]
