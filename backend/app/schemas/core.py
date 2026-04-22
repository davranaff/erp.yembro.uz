from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class OrganizationCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create organization."""


class OrganizationUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update organization."""


class OrganizationReadSchema(OpenSchema, BaseReadSchema):
    """Readable organization response."""


class OrganizationListParams(CRUDBaseParams):
    """Pagination + query params for organization list."""


class OrganizationListResponse(CRUDListResponse[OrganizationReadSchema]):
    """Paginated organization response."""


class DepartmentModuleCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create department module."""


class DepartmentModuleUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update department module."""


class DepartmentModuleReadSchema(OpenSchema, BaseReadSchema):
    """Readable department module response."""


class DepartmentModuleListParams(CRUDBaseParams):
    """Pagination + query params for department module list."""


class DepartmentModuleListResponse(CRUDListResponse[DepartmentModuleReadSchema]):
    """Paginated department module response."""


class WorkspaceResourceReadSchema(OpenSchema, BaseReadSchema):
    """Readable workspace resource response."""


class WorkspaceModuleMetaSchema(OpenSchema):
    """Data-driven workspace module with its resources."""


class WorkspaceModuleListResponse(CRUDListResponse[WorkspaceModuleMetaSchema]):
    """Workspace module metadata response."""


class DepartmentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create department."""


class DepartmentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update department."""


class DepartmentReadSchema(OpenSchema, BaseReadSchema):
    """Readable department response."""


class DepartmentListParams(CRUDBaseParams):
    """Pagination + query params for department list."""


class DepartmentListResponse(CRUDListResponse[DepartmentReadSchema]):
    """Paginated department response."""


class WarehouseCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create warehouse."""


class WarehouseUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update warehouse."""


class WarehouseReadSchema(OpenSchema, BaseReadSchema):
    """Readable warehouse response."""


class WarehouseListParams(CRUDBaseParams):
    """Pagination + query params for warehouse list."""


class WarehouseListResponse(CRUDListResponse[WarehouseReadSchema]):
    """Paginated warehouse response."""


class ClientCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create client."""


class ClientUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update client."""


class ClientReadSchema(OpenSchema, BaseReadSchema):
    """Readable client response."""


class ClientListParams(CRUDBaseParams):
    """Pagination + query params for client list."""


class ClientListResponse(CRUDListResponse[ClientReadSchema]):
    """Paginated client response."""


class ClientDebtCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create client debt."""


class ClientDebtUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update client debt."""


class ClientDebtReadSchema(OpenSchema, BaseReadSchema):
    """Readable client debt response."""


class ClientDebtListParams(CRUDBaseParams):
    """Pagination + query params for client debt list."""


class ClientDebtListResponse(CRUDListResponse[ClientDebtReadSchema]):
    """Paginated client debt response."""


class CurrencyCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create currency."""


class CurrencyUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update currency."""


class CurrencyReadSchema(OpenSchema, BaseReadSchema):
    """Readable currency response."""


class CurrencyListParams(CRUDBaseParams):
    """Pagination + query params for currency list."""


class CurrencyListResponse(CRUDListResponse[CurrencyReadSchema]):
    """Paginated currency response."""


class CurrencyExchangeRateCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create / upsert a currency exchange rate row."""


class CurrencyExchangeRateUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update a currency exchange rate row."""


class CurrencyExchangeRateReadSchema(OpenSchema, BaseReadSchema):
    """Readable currency exchange rate response."""


class CurrencyExchangeRateListParams(CRUDBaseParams):
    """Pagination + query params for currency exchange rate list."""


class CurrencyExchangeRateListResponse(
    CRUDListResponse[CurrencyExchangeRateReadSchema]
):
    """Paginated currency exchange rate response."""


class PoultryTypeCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create poultry type."""


class PoultryTypeUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update poultry type."""


class PoultryTypeReadSchema(OpenSchema, BaseReadSchema):
    """Readable poultry type response."""


class PoultryTypeListParams(CRUDBaseParams):
    """Pagination + query params for poultry type list."""


class PoultryTypeListResponse(CRUDListResponse[PoultryTypeReadSchema]):
    """Paginated poultry type response."""


class MeasurementUnitCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create measurement unit."""


class MeasurementUnitUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update measurement unit."""


class MeasurementUnitReadSchema(OpenSchema, BaseReadSchema):
    """Readable measurement unit response."""


class MeasurementUnitListParams(CRUDBaseParams):
    """Pagination + query params for measurement unit list."""


class MeasurementUnitListResponse(CRUDListResponse[MeasurementUnitReadSchema]):
    """Paginated measurement unit response."""


class ClientCategoryCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create client category."""


class ClientCategoryUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update client category."""


class ClientCategoryReadSchema(OpenSchema, BaseReadSchema):
    """Readable client category response."""


class ClientCategoryListParams(CRUDBaseParams):
    """Pagination + query params for client category list."""


class ClientCategoryListResponse(CRUDListResponse[ClientCategoryReadSchema]):
    """Paginated client category response."""


__all__ = [
    "OrganizationCreateSchema",
    "OrganizationUpdateSchema",
    "OrganizationReadSchema",
    "OrganizationListParams",
    "OrganizationListResponse",
    "DepartmentModuleCreateSchema",
    "DepartmentModuleUpdateSchema",
    "DepartmentModuleReadSchema",
    "DepartmentModuleListParams",
    "DepartmentModuleListResponse",
    "WorkspaceResourceReadSchema",
    "WorkspaceModuleMetaSchema",
    "WorkspaceModuleListResponse",
    "DepartmentCreateSchema",
    "DepartmentUpdateSchema",
    "DepartmentReadSchema",
    "DepartmentListParams",
    "DepartmentListResponse",
    "WarehouseCreateSchema",
    "WarehouseUpdateSchema",
    "WarehouseReadSchema",
    "WarehouseListParams",
    "WarehouseListResponse",
    "ClientCreateSchema",
    "ClientUpdateSchema",
    "ClientReadSchema",
    "ClientListParams",
    "ClientListResponse",
    "ClientDebtCreateSchema",
    "ClientDebtUpdateSchema",
    "ClientDebtReadSchema",
    "ClientDebtListParams",
    "ClientDebtListResponse",
    "CurrencyCreateSchema",
    "CurrencyUpdateSchema",
    "CurrencyReadSchema",
    "CurrencyListParams",
    "CurrencyListResponse",
    "CurrencyExchangeRateCreateSchema",
    "CurrencyExchangeRateUpdateSchema",
    "CurrencyExchangeRateReadSchema",
    "CurrencyExchangeRateListParams",
    "CurrencyExchangeRateListResponse",
    "PoultryTypeCreateSchema",
    "PoultryTypeUpdateSchema",
    "PoultryTypeReadSchema",
    "PoultryTypeListParams",
    "PoultryTypeListResponse",
    "MeasurementUnitCreateSchema",
    "MeasurementUnitUpdateSchema",
    "MeasurementUnitReadSchema",
    "MeasurementUnitListParams",
    "MeasurementUnitListResponse",
    "ClientCategoryCreateSchema",
    "ClientCategoryUpdateSchema",
    "ClientCategoryReadSchema",
    "ClientCategoryListParams",
    "ClientCategoryListResponse",
]
