from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class FeedTypeCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed type."""


class FeedTypeUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed type."""


class FeedTypeReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed type response."""


class FeedTypeListParams(CRUDBaseParams):
    """Pagination + query params for feed type list."""


class FeedTypeListResponse(CRUDListResponse[FeedTypeReadSchema]):
    """Paginated feed type response."""


class FeedIngredientCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed ingredient."""


class FeedIngredientUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed ingredient."""


class FeedIngredientReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed ingredient response."""


class FeedIngredientListParams(CRUDBaseParams):
    """Pagination + query params for feed ingredient list."""


class FeedIngredientListResponse(CRUDListResponse[FeedIngredientReadSchema]):
    """Paginated feed ingredient response."""


class FeedFormulaCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed formula."""


class FeedFormulaUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed formula."""


class FeedFormulaReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed formula response."""


class FeedFormulaListParams(CRUDBaseParams):
    """Pagination + query params for feed formula list."""


class FeedFormulaListResponse(CRUDListResponse[FeedFormulaReadSchema]):
    """Paginated feed formula response."""


class FeedFormulaIngredientCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed formula ingredient."""


class FeedFormulaIngredientUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed formula ingredient."""


class FeedFormulaIngredientReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed formula ingredient response."""


class FeedFormulaIngredientListParams(CRUDBaseParams):
    """Pagination + query params for feed formula ingredient list."""


class FeedFormulaIngredientListResponse(CRUDListResponse[FeedFormulaIngredientReadSchema]):
    """Paginated feed formula ingredient response."""


class FeedProductionBatchCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed production batch."""


class FeedProductionBatchUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed production batch."""


class FeedProductionBatchReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed production batch response."""


class FeedProductionBatchListParams(CRUDBaseParams):
    """Pagination + query params for feed production batch list."""


class FeedProductionBatchListResponse(CRUDListResponse[FeedProductionBatchReadSchema]):
    """Paginated feed production batch response."""


class FeedProductShipmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed product shipment."""


class FeedProductShipmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed product shipment."""


class FeedProductShipmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed product shipment response."""


class FeedProductShipmentListParams(CRUDBaseParams):
    """Pagination + query params for feed product shipment list."""


class FeedProductShipmentListResponse(CRUDListResponse[FeedProductShipmentReadSchema]):
    """Paginated feed product shipment response."""


class FeedRawArrivalCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed raw arrival."""


class FeedRawArrivalUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed raw arrival."""


class FeedRawArrivalReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed raw arrival response."""


class FeedRawArrivalListParams(CRUDBaseParams):
    """Pagination + query params for feed raw arrival list."""


class FeedRawArrivalListResponse(CRUDListResponse[FeedRawArrivalReadSchema]):
    """Paginated feed raw arrival response."""


class FeedRawConsumptionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed raw consumption."""


class FeedRawConsumptionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed raw consumption."""


class FeedRawConsumptionReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed raw consumption response."""


class FeedRawConsumptionListParams(CRUDBaseParams):
    """Pagination + query params for feed raw consumption list."""


class FeedRawConsumptionListResponse(CRUDListResponse[FeedRawConsumptionReadSchema]):
    """Paginated feed raw consumption response."""


class FeedProductionQualityCheckCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed production quality check."""


class FeedProductionQualityCheckUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed production quality check."""


class FeedProductionQualityCheckReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed production quality check response."""


class FeedProductionQualityCheckListParams(CRUDBaseParams):
    """Pagination + query params for feed production quality check list."""


class FeedProductionQualityCheckListResponse(CRUDListResponse[FeedProductionQualityCheckReadSchema]):
    """Paginated feed production quality check response."""


class FeedMonthlyAnalyticsCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create feed monthly analytics row."""


class FeedMonthlyAnalyticsUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update feed monthly analytics row."""


class FeedMonthlyAnalyticsReadSchema(OpenSchema, BaseReadSchema):
    """Readable feed monthly analytics response."""


class FeedMonthlyAnalyticsListParams(CRUDBaseParams):
    """Pagination + query params for feed monthly analytics list."""


class FeedMonthlyAnalyticsListResponse(CRUDListResponse[FeedMonthlyAnalyticsReadSchema]):
    """Paginated feed monthly analytics response."""


__all__ = [
    "FeedTypeCreateSchema",
    "FeedTypeUpdateSchema",
    "FeedTypeReadSchema",
    "FeedTypeListParams",
    "FeedTypeListResponse",
    "FeedIngredientCreateSchema",
    "FeedIngredientUpdateSchema",
    "FeedIngredientReadSchema",
    "FeedIngredientListParams",
    "FeedIngredientListResponse",
    "FeedFormulaCreateSchema",
    "FeedFormulaUpdateSchema",
    "FeedFormulaReadSchema",
    "FeedFormulaListParams",
    "FeedFormulaListResponse",
    "FeedFormulaIngredientCreateSchema",
    "FeedFormulaIngredientUpdateSchema",
    "FeedFormulaIngredientReadSchema",
    "FeedFormulaIngredientListParams",
    "FeedFormulaIngredientListResponse",
    "FeedProductionBatchCreateSchema",
    "FeedProductionBatchUpdateSchema",
    "FeedProductionBatchReadSchema",
    "FeedProductionBatchListParams",
    "FeedProductionBatchListResponse",
    "FeedProductShipmentCreateSchema",
    "FeedProductShipmentUpdateSchema",
    "FeedProductShipmentReadSchema",
    "FeedProductShipmentListParams",
    "FeedProductShipmentListResponse",
    "FeedRawArrivalCreateSchema",
    "FeedRawArrivalUpdateSchema",
    "FeedRawArrivalReadSchema",
    "FeedRawArrivalListParams",
    "FeedRawArrivalListResponse",
    "FeedRawConsumptionCreateSchema",
    "FeedRawConsumptionUpdateSchema",
    "FeedRawConsumptionReadSchema",
    "FeedRawConsumptionListParams",
    "FeedRawConsumptionListResponse",
    "FeedProductionQualityCheckCreateSchema",
    "FeedProductionQualityCheckUpdateSchema",
    "FeedProductionQualityCheckReadSchema",
    "FeedProductionQualityCheckListParams",
    "FeedProductionQualityCheckListResponse",
    "FeedMonthlyAnalyticsCreateSchema",
    "FeedMonthlyAnalyticsUpdateSchema",
    "FeedMonthlyAnalyticsReadSchema",
    "FeedMonthlyAnalyticsListParams",
    "FeedMonthlyAnalyticsListResponse",
]
