from __future__ import annotations

from app.repositories.base import BaseRepository


class FeedTypeRepository(BaseRepository[dict[str, object]]):
    table = "feed_types"


class FeedIngredientRepository(BaseRepository[dict[str, object]]):
    table = "feed_ingredients"


class FeedFormulaRepository(BaseRepository[dict[str, object]]):
    table = "feed_formulas"


class FeedFormulaIngredientRepository(BaseRepository[dict[str, object]]):
    table = "feed_formula_ingredients"


class FeedProductionBatchRepository(BaseRepository[dict[str, object]]):
    table = "feed_production_batches"


class FeedProductShipmentRepository(BaseRepository[dict[str, object]]):
    table = "feed_product_shipments"


class FeedRawArrivalRepository(BaseRepository[dict[str, object]]):
    table = "feed_raw_arrivals"


class FeedRawConsumptionRepository(BaseRepository[dict[str, object]]):
    table = "feed_raw_consumptions"


class FeedConsumptionRepository(BaseRepository[dict[str, object]]):
    table = "feed_consumptions"


class FeedProductionQualityCheckRepository(BaseRepository[dict[str, object]]):
    table = "feed_production_quality_checks"


class FeedMonthlyAnalyticsRepository(BaseRepository[dict[str, object]]):
    table = "feed_monthly_analytics"


__all__ = [
    "FeedTypeRepository",
    "FeedIngredientRepository",
    "FeedFormulaRepository",
    "FeedFormulaIngredientRepository",
    "FeedProductionBatchRepository",
    "FeedProductShipmentRepository",
    "FeedRawArrivalRepository",
    "FeedRawConsumptionRepository",
    "FeedConsumptionRepository",
    "FeedProductionQualityCheckRepository",
    "FeedMonthlyAnalyticsRepository",
]
