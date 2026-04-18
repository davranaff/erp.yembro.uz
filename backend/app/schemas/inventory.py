from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class StockMovementCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create stock movement."""


class StockMovementUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update stock movement."""


class StockMovementReadSchema(OpenSchema, BaseReadSchema):
    """Readable stock movement response."""


class StockMovementListParams(CRUDBaseParams):
    """Pagination + query params for stock movement list."""


class StockMovementListResponse(CRUDListResponse[StockMovementReadSchema]):
    """Paginated stock movement response."""


class StockTakeCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create stock take."""


class StockTakeUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update stock take."""


class StockTakeReadSchema(OpenSchema, BaseReadSchema):
    """Readable stock take response."""


class StockTakeLineCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create stock take line."""


class StockTakeLineUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update stock take line."""


class StockTakeLineReadSchema(OpenSchema, BaseReadSchema):
    """Readable stock take line response."""


class StockReorderLevelCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create stock reorder level."""


class StockReorderLevelUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update stock reorder level."""


class StockReorderLevelReadSchema(OpenSchema, BaseReadSchema):
    """Readable stock reorder level response."""


__all__ = [
    "StockMovementCreateSchema",
    "StockMovementUpdateSchema",
    "StockMovementReadSchema",
    "StockMovementListParams",
    "StockMovementListResponse",
    "StockTakeCreateSchema",
    "StockTakeUpdateSchema",
    "StockTakeReadSchema",
    "StockTakeLineCreateSchema",
    "StockTakeLineUpdateSchema",
    "StockTakeLineReadSchema",
    "StockReorderLevelCreateSchema",
    "StockReorderLevelUpdateSchema",
    "StockReorderLevelReadSchema",
]
