from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class FactoryFlockCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create a factory flock."""


class FactoryFlockUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a factory flock."""


class FactoryFlockReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory flock response."""


class FactoryFlockListParams(CRUDBaseParams):
    """Pagination + query params for factory flock list."""


class FactoryFlockListResponse(CRUDListResponse[FactoryFlockReadSchema]):
    """Paginated factory flock response."""


class FactoryDailyLogCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create a factory daily log."""


class FactoryDailyLogUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a factory daily log."""


class FactoryDailyLogReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory daily log response."""


class FactoryDailyLogListParams(CRUDBaseParams):
    """Pagination + query params for factory daily log list."""


class FactoryDailyLogListResponse(CRUDListResponse[FactoryDailyLogReadSchema]):
    """Paginated factory daily log response."""


class FactoryShipmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create a factory shipment."""


class FactoryShipmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a factory shipment."""


class FactoryShipmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory shipment response."""


class FactoryShipmentListParams(CRUDBaseParams):
    """Pagination + query params for factory shipment list."""


class FactoryShipmentListResponse(CRUDListResponse[FactoryShipmentReadSchema]):
    """Paginated factory shipment response."""


class FactoryMedicineUsageCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create a factory medicine usage."""


class FactoryMedicineUsageUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a factory medicine usage."""


class FactoryMedicineUsageReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory medicine usage response."""


class FactoryMedicineUsageListParams(CRUDBaseParams):
    """Pagination + query params for factory medicine usage list."""


class FactoryMedicineUsageListResponse(CRUDListResponse[FactoryMedicineUsageReadSchema]):
    """Paginated factory medicine usage response."""



class FactoryVaccinationPlanCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create a factory vaccination plan."""


class FactoryVaccinationPlanUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a factory vaccination plan."""


class FactoryVaccinationPlanReadSchema(OpenSchema, BaseReadSchema):
    """Readable factory vaccination plan response."""


class FactoryVaccinationPlanListParams(CRUDBaseParams):
    """Pagination + query params for factory vaccination plan list."""


class FactoryVaccinationPlanListResponse(CRUDListResponse[FactoryVaccinationPlanReadSchema]):
    """Paginated factory vaccination plan response."""
