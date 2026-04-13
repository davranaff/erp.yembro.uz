from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class EmployeeCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create employee."""


class EmployeeUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update employee."""


class EmployeeReadSchema(OpenSchema, BaseReadSchema):
    """Readable employee response."""


class EmployeeListParams(CRUDBaseParams):
    """Pagination + query params for employee list."""


class EmployeeListResponse(CRUDListResponse[EmployeeReadSchema]):
    """Paginated employee response."""


class PositionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create position."""


class PositionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update position."""


class PositionReadSchema(OpenSchema, BaseReadSchema):
    """Readable position response."""


class PositionListParams(CRUDBaseParams):
    """Pagination + query params for position list."""


class PositionListResponse(CRUDListResponse[PositionReadSchema]):
    """Paginated position response."""


class RoleCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create role."""


class RoleUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update role."""


class RoleReadSchema(OpenSchema, BaseReadSchema):
    """Readable role response."""


class RoleListParams(CRUDBaseParams):
    """Pagination + query params for role list."""


class RoleListResponse(CRUDListResponse[RoleReadSchema]):
    """Paginated role response."""


class PermissionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create permission."""


class PermissionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update permission."""


class PermissionReadSchema(OpenSchema, BaseReadSchema):
    """Readable permission response."""


class PermissionListParams(CRUDBaseParams):
    """Pagination + query params for permission list."""


class PermissionListResponse(CRUDListResponse[PermissionReadSchema]):
    """Paginated permission response."""


__all__ = [
    "EmployeeCreateSchema",
    "EmployeeUpdateSchema",
    "EmployeeReadSchema",
    "EmployeeListParams",
    "EmployeeListResponse",
    "PositionCreateSchema",
    "PositionUpdateSchema",
    "PositionReadSchema",
    "PositionListParams",
    "PositionListResponse",
    "RoleCreateSchema",
    "RoleUpdateSchema",
    "RoleReadSchema",
    "RoleListParams",
    "RoleListResponse",
    "PermissionCreateSchema",
    "PermissionUpdateSchema",
    "PermissionReadSchema",
    "PermissionListParams",
    "PermissionListResponse",
]
