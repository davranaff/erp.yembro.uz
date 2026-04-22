from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.slaughter import (
    SlaughterArrivalRepository,
    SlaughterProcessingRepository,
    SlaughterQualityCheckRepository,
    SlaughterSemiProductRepository,
    SlaughterSemiProductShipmentRepository,
)
from app.services.slaughter import (
    SlaughterArrivalService,
    SlaughterProcessingService,
    SlaughterQualityCheckService,
    SlaughterSemiProductShipmentService,
    SlaughterSemiProductService,
)


router = APIRouter(prefix="/slaughter", tags=["slaughter"])

router.include_router(
    build_crud_router(
        prefix="arrivals",
        service_factory=lambda db: SlaughterArrivalService(SlaughterArrivalRepository(db)),
        permission_prefix="slaughter_arrival",
        tags=["slaughter-arrival"],
    )
)

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

register_module_stats_route(
    router,
    module="slaughter",
    label="Slaughter",
    tables=(
        ModuleStatsTable(key="arrivals", label="Arrivals", table="slaughter_arrivals"),
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
    ),
)

__all__ = ["router"]
