from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class MedicineBatchCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create medicine batch."""


class MedicineBatchUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update medicine batch."""


class MedicineBatchReadSchema(OpenSchema, BaseReadSchema):
    """Readable medicine batch response."""


class MedicineBatchListParams(CRUDBaseParams):
    """Pagination + query params for medicine batch list."""


class MedicineBatchListResponse(CRUDListResponse[MedicineBatchReadSchema]):
    """Paginated medicine batch response."""


class MedicineTypeCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create medicine type."""


class MedicineTypeUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update medicine type."""


class MedicineTypeReadSchema(OpenSchema, BaseReadSchema):
    """Readable medicine type response."""


class MedicineTypeListParams(CRUDBaseParams):
    """Pagination + query params for medicine type list."""


class MedicineTypeListResponse(CRUDListResponse[MedicineTypeReadSchema]):
    """Paginated medicine type response."""


class MedicineConsumptionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create medicine consumption."""


class MedicineConsumptionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update medicine consumption."""


class MedicineConsumptionReadSchema(OpenSchema, BaseReadSchema):
    """Readable medicine consumption response."""


class MedicineConsumptionListParams(CRUDBaseParams):
    """Pagination + query params for medicine consumption list."""


class MedicineConsumptionListResponse(CRUDListResponse[MedicineConsumptionReadSchema]):
    """Paginated medicine consumption response."""


__all__ = [
    "MedicineBatchCreateSchema",
    "MedicineBatchUpdateSchema",
    "MedicineBatchReadSchema",
    "MedicineBatchListParams",
    "MedicineBatchListResponse",
    "MedicineTypeCreateSchema",
    "MedicineTypeUpdateSchema",
    "MedicineTypeReadSchema",
    "MedicineTypeListParams",
    "MedicineTypeListResponse",
    "MedicineConsumptionCreateSchema",
    "MedicineConsumptionUpdateSchema",
    "MedicineConsumptionReadSchema",
    "MedicineConsumptionListParams",
    "MedicineConsumptionListResponse",
]
