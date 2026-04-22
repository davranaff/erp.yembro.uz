from __future__ import annotations

from app.repositories.base import BaseRepository


class ChickShipmentRepository(BaseRepository[dict[str, object]]):
    table = "chick_shipments"


class IncubationBatchRepository(BaseRepository[dict[str, object]]):
    table = "incubation_batches"


class IncubationRunRepository(BaseRepository[dict[str, object]]):
    table = "incubation_runs"


__all__ = [
    "ChickShipmentRepository",
    "IncubationBatchRepository",
    "IncubationRunRepository",
]
