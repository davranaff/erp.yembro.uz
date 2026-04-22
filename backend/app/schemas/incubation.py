from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class ChickShipmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create chick shipment."""


class ChickShipmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update chick shipment."""


class ChickShipmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable chick shipment response."""


class ChickShipmentListParams(CRUDBaseParams):
    """Pagination + query params for chick shipment list."""


class ChickShipmentListResponse(CRUDListResponse[ChickShipmentReadSchema]):
    """Paginated chick shipment response."""


class IncubationBatchCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create incubation batch."""


class IncubationBatchUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update incubation batch."""


class IncubationBatchReadSchema(OpenSchema, BaseReadSchema):
    """Readable incubation batch response."""


class IncubationBatchListParams(CRUDBaseParams):
    """Pagination + query params for incubation batch list."""


class IncubationBatchListResponse(CRUDListResponse[IncubationBatchReadSchema]):
    """Paginated incubation batch response."""


class IncubationRunCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create incubation run."""


class IncubationRunUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update incubation run."""


class IncubationRunReadSchema(OpenSchema, BaseReadSchema):
    """Readable incubation run response."""


class IncubationRunListParams(CRUDBaseParams):
    """Pagination + query params for incubation run list."""


class IncubationRunListResponse(CRUDListResponse[IncubationRunReadSchema]):
    """Paginated incubation run response."""












__all__ = [
    "ChickShipmentCreateSchema",
    "ChickShipmentUpdateSchema",
    "ChickShipmentReadSchema",
    "ChickShipmentListParams",
    "ChickShipmentListResponse",
    "IncubationBatchCreateSchema",
    "IncubationBatchUpdateSchema",
    "IncubationBatchReadSchema",
    "IncubationBatchListParams",
    "IncubationBatchListResponse",
    "IncubationRunCreateSchema",
    "IncubationRunUpdateSchema",
    "IncubationRunReadSchema",
    "IncubationRunListParams",
    "IncubationRunListResponse",
]
