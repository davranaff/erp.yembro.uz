from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class EggProductionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create egg production."""


class EggProductionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update egg production."""


class EggProductionReadSchema(OpenSchema, BaseReadSchema):
    """Readable egg production response."""


class EggProductionListParams(CRUDBaseParams):
    """Pagination + query params for egg production list."""


class EggProductionListResponse(CRUDListResponse[EggProductionReadSchema]):
    """Paginated egg production response."""


class EggShipmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create egg shipment."""


class EggShipmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update egg shipment."""


class EggShipmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable egg shipment response."""


class EggShipmentListParams(CRUDBaseParams):
    """Pagination + query params for egg shipment list."""


class EggShipmentListResponse(CRUDListResponse[EggShipmentReadSchema]):
    """Paginated egg shipment response."""


class EggQualityCheckCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create egg quality check."""


class EggQualityCheckUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update egg quality check."""


class EggQualityCheckReadSchema(OpenSchema, BaseReadSchema):
    """Readable egg quality check response."""


class EggQualityCheckListParams(CRUDBaseParams):
    """Pagination + query params for egg quality check list."""


class EggQualityCheckListResponse(CRUDListResponse[EggQualityCheckReadSchema]):
    """Paginated egg quality check response."""


class EggMonthlyAnalyticsCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create egg monthly analytics."""


class EggMonthlyAnalyticsUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update egg monthly analytics."""


class EggMonthlyAnalyticsReadSchema(OpenSchema, BaseReadSchema):
    """Readable egg monthly analytics response."""


class EggMonthlyAnalyticsListParams(CRUDBaseParams):
    """Pagination + query params for egg monthly analytics list."""


class EggMonthlyAnalyticsListResponse(CRUDListResponse[EggMonthlyAnalyticsReadSchema]):
    """Paginated egg monthly analytics response."""


__all__ = [
    "EggProductionCreateSchema",
    "EggProductionUpdateSchema",
    "EggProductionReadSchema",
    "EggProductionListParams",
    "EggProductionListResponse",
    "EggShipmentCreateSchema",
    "EggShipmentUpdateSchema",
    "EggShipmentReadSchema",
    "EggShipmentListParams",
    "EggShipmentListResponse",
    "EggQualityCheckCreateSchema",
    "EggQualityCheckUpdateSchema",
    "EggQualityCheckReadSchema",
    "EggQualityCheckListParams",
    "EggQualityCheckListResponse",
    "EggMonthlyAnalyticsCreateSchema",
    "EggMonthlyAnalyticsUpdateSchema",
    "EggMonthlyAnalyticsReadSchema",
    "EggMonthlyAnalyticsListParams",
    "EggMonthlyAnalyticsListResponse",
]
