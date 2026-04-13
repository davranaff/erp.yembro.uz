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


__all__ = [
    "StockMovementCreateSchema",
    "StockMovementUpdateSchema",
    "StockMovementReadSchema",
    "StockMovementListParams",
    "StockMovementListResponse",
]
