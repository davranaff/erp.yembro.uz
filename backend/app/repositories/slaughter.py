from __future__ import annotations

from app.repositories.base import BaseRepository


class SlaughterArrivalRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_arrivals"


class SlaughterProcessingRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_processings"


class SlaughterSemiProductRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_semi_products"


class SlaughterSemiProductShipmentRepository(BaseRepository[dict[str, object]]):
    table = "slaughter_semi_product_shipments"


__all__ = [
    "SlaughterArrivalRepository",
    "SlaughterProcessingRepository",
    "SlaughterSemiProductRepository",
    "SlaughterSemiProductShipmentRepository",
]
