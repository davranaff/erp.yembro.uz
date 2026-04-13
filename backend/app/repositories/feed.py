from __future__ import annotations

from app.repositories.base import BaseRepository


class FeedTypeRepository(BaseRepository[dict[str, object]]):
    table = "feed_types"


class FeedIngredientRepository(BaseRepository[dict[str, object]]):
    table = "feed_ingredients"


class FeedArrivalRepository(BaseRepository[dict[str, object]]):
    table = "feed_arrivals"


class FeedConsumptionRepository(BaseRepository[dict[str, object]]):
    table = "feed_consumptions"


class FeedFormulaRepository(BaseRepository[dict[str, object]]):
    table = "feed_formulas"


class FeedFormulaIngredientRepository(BaseRepository[dict[str, object]]):
    table = "feed_formula_ingredients"


class FeedRawArrivalRepository(BaseRepository[dict[str, object]]):
    table = "feed_raw_arrivals"


class FeedProductionBatchRepository(BaseRepository[dict[str, object]]):
    table = "feed_production_batches"


class FeedRawConsumptionRepository(BaseRepository[dict[str, object]]):
    table = "feed_raw_consumptions"


class FeedProductShipmentRepository(BaseRepository[dict[str, object]]):
    table = "feed_product_shipments"


__all__ = [
    "FeedTypeRepository",
    "FeedIngredientRepository",
    "FeedArrivalRepository",
    "FeedConsumptionRepository",
    "FeedFormulaRepository",
    "FeedFormulaIngredientRepository",
    "FeedRawArrivalRepository",
    "FeedProductionBatchRepository",
    "FeedRawConsumptionRepository",
    "FeedProductShipmentRepository",
]
