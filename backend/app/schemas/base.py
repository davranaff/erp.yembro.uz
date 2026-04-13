from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field


try:
    from pydantic import ConfigDict  # type: ignore

    class BaseSchema(BaseModel):
        model_config = ConfigDict(from_attributes=True)

except Exception:  # pragma: no cover
    class BaseSchema(BaseModel):
        class Config:
            orm_mode = True


class OpenSchema(BaseSchema):
    """Base schema that allows transporting arbitrary fields."""

    try:
        model_config = ConfigDict(from_attributes=True, extra="allow")
    except Exception:  # pragma: no cover
        class Config:
            orm_mode = True
            arbitrary_types_allowed = True
            extra = "allow"


class IDSchema(BaseSchema):
    id: UUID = Field(...)


class AuditSchema(BaseSchema):
    created_at: datetime | None = None
    updated_at: datetime | None = None


class BaseReadSchema(IDSchema, AuditSchema):
    """Base outgoing schema."""


class BaseCreateSchema(BaseSchema):
    """Base input schema for create operations."""


class BaseUpdateSchema(BaseSchema):
    try:
        model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
    except Exception:  # pragma: no cover
        class Config:
            arbitrary_types_allowed = True


class PageParams(BaseSchema):
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ListResponse(BaseSchema):
    items: list[Any]
    total: int
    limit: int
    offset: int
    has_more: bool

    @classmethod
    def from_items(cls, items: list[Any], total: int, limit: int, offset: int) -> "ListResponse":
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(items)) < total,
        )


class MessageSchema(BaseSchema):
    detail: str


class CRUDBaseParams(BaseSchema):
    """Base set of query params for list/filter endpoints."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)
    q: str | None = Field(default=None, max_length=255)
    order_by: str | None = Field(default=None, max_length=255)
    order_dir: str = Field(default="asc")


class CRUDCreateSchema(BaseCreateSchema):
    """Base create payload schema."""


class CRUDUpdateSchema(BaseUpdateSchema):
    """Base update payload schema."""


class CRUDReadSchema(BaseReadSchema):
    """Alias for read schemas with id + audit fields."""


T = TypeVar("T")


class PaginatedSchema(BaseSchema, Generic[T]):
    """Common paginated response for CRUD list endpoints."""

    items: list[T]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=1000)
    offset: int = Field(ge=0)
    has_more: bool

    @classmethod
    def from_items(cls, items: list[T], total: int, limit: int, offset: int) -> "PaginatedSchema[T]":
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_more=(offset + len(items)) < total,
        )


class CRUDListResponse(PaginatedSchema[T], Generic[T]):
    pass


class MessageWithPayloadSchema(BaseSchema):
    message: str
    data: Any | None = None


class IDResultSchema(BaseSchema):
    id: UUID
    deleted: bool = False


class ErrorPayloadSchema(BaseSchema):
    code: str
    message: str
    details: Any | None = None


class ApiResponseSchema(BaseSchema, Generic[T]):
    ok: bool
    data: T | None = None
    error: ErrorPayloadSchema | None = None
