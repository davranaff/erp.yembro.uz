from __future__ import annotations

from app.repositories.base import BaseRepository


class MedicineArrivalRepository(BaseRepository[dict[str, object]]):
    table = "medicine_arrivals"


class MedicineBatchRepository(BaseRepository[dict[str, object]]):
    table = "medicine_batches"


class MedicineConsumptionRepository(BaseRepository[dict[str, object]]):
    table = "medicine_consumptions"


class MedicineTypeRepository(BaseRepository[dict[str, object]]):
    table = "medicine_types"


__all__ = [
    "MedicineArrivalRepository",
    "MedicineBatchRepository",
    "MedicineConsumptionRepository",
    "MedicineTypeRepository",
]
