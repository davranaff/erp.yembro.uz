from __future__ import annotations

from app.repositories.base import BaseRepository


class ChickArrivalRepository(BaseRepository[dict[str, object]]):
    table = "chick_arrivals"


class ChickShipmentRepository(BaseRepository[dict[str, object]]):
    table = "chick_shipments"


class IncubationBatchRepository(BaseRepository[dict[str, object]]):
    table = "incubation_batches"


class IncubationRunRepository(BaseRepository[dict[str, object]]):
    table = "incubation_runs"


class IncubationMonthlyAnalyticsRepository(BaseRepository[dict[str, object]]):
    table = "incubation_monthly_analytics"


class FactoryMonthlyAnalyticsRepository(BaseRepository[dict[str, object]]):
    table = "factory_monthly_analytics"


__all__ = [
    "ChickArrivalRepository",
    "ChickShipmentRepository",
    "IncubationBatchRepository",
    "IncubationRunRepository",
    "IncubationMonthlyAnalyticsRepository",
    "FactoryMonthlyAnalyticsRepository",
]
