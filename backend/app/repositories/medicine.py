from __future__ import annotations

from app.repositories.base import BaseRepository


class MedicineBatchRepository(BaseRepository[dict[str, object]]):
    table = "medicine_batches"


class MedicineTypeRepository(BaseRepository[dict[str, object]]):
    table = "medicine_types"


__all__ = [
    "MedicineBatchRepository",
    "MedicineTypeRepository",
]
