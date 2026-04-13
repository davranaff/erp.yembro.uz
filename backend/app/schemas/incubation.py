from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class ChickArrivalCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create chick arrival."""


class ChickArrivalUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update chick arrival."""


class ChickArrivalReadSchema(OpenSchema, BaseReadSchema):
    """Readable chick arrival response."""


class ChickArrivalListParams(CRUDBaseParams):
    """Pagination + query params for chick arrival list."""


class ChickArrivalListResponse(CRUDListResponse[ChickArrivalReadSchema]):
    """Paginated chick arrival response."""


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


class IncubationMonthlyAnalyticsCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create incubation monthly analytics."""


class IncubationMonthlyAnalyticsUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update incubation monthly analytics."""


class IncubationMonthlyAnalyticsReadSchema(OpenSchema, BaseReadSchema):
    """Readable incubation monthly analytics response."""


class IncubationMonthlyAnalyticsListParams(CRUDBaseParams):
    """Pagination + query params for incubation monthly analytics list."""


class IncubationMonthlyAnalyticsListResponse(CRUDListResponse[IncubationMonthlyAnalyticsReadSchema]):
    """Paginated incubation monthly analytics response."""


class FactoryMonthlyAnalyticsCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create factory monthly analytics."""


class FactoryMonthlyAnalyticsUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update factory monthly analytics."""


class FactoryMonthlyAnalyticsReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory monthly analytics response."""


class FactoryMonthlyAnalyticsListParams(CRUDBaseParams):
    """Pagination + query params for factory monthly analytics list."""


class FactoryMonthlyAnalyticsListResponse(CRUDListResponse[FactoryMonthlyAnalyticsReadSchema]):
    """Paginated factory monthly analytics response."""


__all__ = [
    "ChickArrivalCreateSchema",
    "ChickArrivalUpdateSchema",
    "ChickArrivalReadSchema",
    "ChickArrivalListParams",
    "ChickArrivalListResponse",
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
    "IncubationMonthlyAnalyticsCreateSchema",
    "IncubationMonthlyAnalyticsUpdateSchema",
    "IncubationMonthlyAnalyticsReadSchema",
    "IncubationMonthlyAnalyticsListParams",
    "IncubationMonthlyAnalyticsListResponse",
    "FactoryMonthlyAnalyticsCreateSchema",
    "FactoryMonthlyAnalyticsUpdateSchema",
    "FactoryMonthlyAnalyticsReadSchema",
    "FactoryMonthlyAnalyticsListParams",
    "FactoryMonthlyAnalyticsListResponse",
]
