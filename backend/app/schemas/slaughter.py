from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class SlaughterProcessingCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create slaughter processing."""


class SlaughterProcessingUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update slaughter processing."""


class SlaughterProcessingReadSchema(OpenSchema, BaseReadSchema):
    """Readable slaughter processing response."""


class SlaughterProcessingListParams(CRUDBaseParams):
    """Pagination + query params for slaughter processing list."""


class SlaughterProcessingListResponse(CRUDListResponse[SlaughterProcessingReadSchema]):
    """Paginated slaughter processing response."""


class SlaughterSemiProductCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create slaughter semi-product."""


class SlaughterSemiProductUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update slaughter semi-product."""


class SlaughterSemiProductReadSchema(OpenSchema, BaseReadSchema):
    """Readable slaughter semi-product response."""


class SlaughterSemiProductListParams(CRUDBaseParams):
    """Pagination + query params for slaughter semi-product list."""


class SlaughterSemiProductListResponse(CRUDListResponse[SlaughterSemiProductReadSchema]):
    """Paginated slaughter semi-product response."""


class SlaughterSemiProductShipmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create slaughter semi-product shipment."""


class SlaughterSemiProductShipmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update slaughter semi-product shipment."""


class SlaughterSemiProductShipmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable slaughter semi-product shipment response."""


class SlaughterSemiProductShipmentListParams(CRUDBaseParams):
    """Pagination + query params for slaughter semi-product shipment list."""


class SlaughterSemiProductShipmentListResponse(CRUDListResponse[SlaughterSemiProductShipmentReadSchema]):
    """Paginated slaughter semi-product shipment response."""


class SlaughterQualityCheckCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create slaughter quality check."""


class SlaughterQualityCheckUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update slaughter quality check."""


class SlaughterQualityCheckReadSchema(OpenSchema, BaseReadSchema):
    """Readable slaughter quality check response."""


class SlaughterQualityCheckListParams(CRUDBaseParams):
    """Pagination + query params for slaughter quality check list."""


class SlaughterQualityCheckListResponse(CRUDListResponse[SlaughterQualityCheckReadSchema]):
    """Paginated slaughter quality check response."""


class SlaughterMonthlyAnalyticsCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create slaughter monthly analytics."""


class SlaughterMonthlyAnalyticsUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update slaughter monthly analytics."""


class SlaughterMonthlyAnalyticsReadSchema(OpenSchema, BaseReadSchema):
    """Readable slaughter monthly analytics response."""


class SlaughterMonthlyAnalyticsListParams(CRUDBaseParams):
    """Pagination + query params for slaughter monthly analytics list."""


class SlaughterMonthlyAnalyticsListResponse(
    CRUDListResponse[SlaughterMonthlyAnalyticsReadSchema]
):
    """Paginated slaughter monthly analytics response."""


__all__ = [
    "SlaughterProcessingCreateSchema",
    "SlaughterProcessingUpdateSchema",
    "SlaughterProcessingReadSchema",
    "SlaughterProcessingListParams",
    "SlaughterProcessingListResponse",
    "SlaughterSemiProductCreateSchema",
    "SlaughterSemiProductUpdateSchema",
    "SlaughterSemiProductReadSchema",
    "SlaughterSemiProductListParams",
    "SlaughterSemiProductListResponse",
    "SlaughterSemiProductShipmentCreateSchema",
    "SlaughterSemiProductShipmentUpdateSchema",
    "SlaughterSemiProductShipmentReadSchema",
    "SlaughterSemiProductShipmentListParams",
    "SlaughterSemiProductShipmentListResponse",
    "SlaughterQualityCheckCreateSchema",
    "SlaughterQualityCheckUpdateSchema",
    "SlaughterQualityCheckReadSchema",
    "SlaughterQualityCheckListParams",
    "SlaughterQualityCheckListResponse",
    "SlaughterMonthlyAnalyticsCreateSchema",
    "SlaughterMonthlyAnalyticsUpdateSchema",
    "SlaughterMonthlyAnalyticsReadSchema",
    "SlaughterMonthlyAnalyticsListParams",
    "SlaughterMonthlyAnalyticsListResponse",
]
