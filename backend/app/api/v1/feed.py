from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.feed import (
    FeedFormulaIngredientRepository,
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedMonthlyAnalyticsRepository,
    FeedProductionBatchRepository,
    FeedProductionQualityCheckRepository,
    FeedProductShipmentRepository,
    FeedRawArrivalRepository,
    FeedRawConsumptionRepository,
    FeedTypeRepository,
)
from app.services.feed import (
    FeedFormulaIngredientService,
    FeedFormulaService,
    FeedIngredientService,
    FeedMonthlyAnalyticsService,
    FeedProductShipmentService,
    FeedProductionBatchService,
    FeedProductionQualityCheckService,
    FeedRawArrivalService,
    FeedRawConsumptionService,
    FeedTypeService,
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
        prefix="formula-ingredients",
        service_factory=lambda db: FeedFormulaIngredientService(FeedFormulaIngredientRepository(db)),
        permission_prefix="feed_formula_ingredient",
        tags=["feed-formula-ingredient"],
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
        prefix="monthly-analytics",
        service_factory=lambda db: FeedMonthlyAnalyticsService(FeedMonthlyAnalyticsRepository(db)),
        permission_prefix="feed_monthly_analytics",
        tags=["feed-monthly-analytics"],
    )
)

register_module_stats_route(
    router,
    module="feed",
    label="Feed",
    tables=(
        ModuleStatsTable(key="types", label="Types", table="feed_types"),
        ModuleStatsTable(key="ingredients", label="Ingredients", table="feed_ingredients"),
        ModuleStatsTable(key="formulas", label="Formulas", table="feed_formulas"),
        ModuleStatsTable(
            key="formula_ingredients",
            label="Formula Ingredients",
            table="feed_formula_ingredients",
        ),
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
            key="monthly_analytics",
            label="Monthly Analytics",
            table="feed_monthly_analytics",
        ),
    ),
)

__all__ = ["router"]
