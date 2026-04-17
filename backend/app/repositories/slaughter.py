from __future__ import annotations

from app.repositories.base import BaseRepository


class SlaughterProcessingRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_processings"


class SlaughterSemiProductRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_semi_products"


class SlaughterSemiProductShipmentRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_semi_product_shipments"


class SlaughterQualityCheckRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_quality_checks"


class SlaughterMonthlyAnalyticsRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_monthly_analytics"


__all__ = [
    "SlaughterProcessingRepository",
    "SlaughterSemiProductRepository",
    "SlaughterSemiProductShipmentRepository",
    "SlaughterQualityCheckRepository",
    "SlaughterMonthlyAnalyticsRepository",
]
