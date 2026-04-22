from __future__ import annotations

from app.repositories.base import BaseRepository


class EggProductionRepository(BaseRepository[dict[str, object]]):
    table = "egg_production"


class EggShipmentRepository(BaseRepository[dict[str, object]]):
    table = "egg_shipments"


class EggQualityCheckRepository(BaseRepository[dict[str, object]]):
    table = "egg_quality_checks"


__all__ = [
    "EggProductionRepository",
    "EggShipmentRepository",
    "EggQualityCheckRepository",
]
