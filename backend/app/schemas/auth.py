from __future__ import annotations

from app.schemas.base import OpenSchema


class AuthLoginRequestSchema(OpenSchema):
    username: str
    password: str


class AuthLoginResponseSchema(OpenSchema):
    employeeId: str
    organizationId: str
    departmentId: str | None = None
    departmentModuleKey: str | None = None
    headsAnyDepartment: bool = False
    username: str
    roles: list[str]
    permissions: list[str]
    allowedDepartmentIds: list[str] | None = None
    allowedWarehouseIds: list[str] | None = None
    isOrgAdmin: bool = False
    accessToken: str | None = None
    refreshToken: str | None = None
    expiresAt: str | None = None


class AuthRefreshRequestSchema(OpenSchema):
    refreshToken: str


class AuthProfileSchema(OpenSchema):
    employeeId: str
    organizationId: str
    departmentId: str | None = None
    departmentModuleKey: str | None = None
    headsAnyDepartment: bool = False
    username: str
    firstName: str
    lastName: str
    email: str | None = None
    phone: str | None = None
    roles: list[str]
    permissions: list[str]
    allowedDepartmentIds: list[str] | None = None
    allowedWarehouseIds: list[str] | None = None
    isOrgAdmin: bool = False


class AuthProfileUpdateSchema(OpenSchema):
    firstName: str
    lastName: str
    email: str | None = None
    phone: str | None = None
    currentPassword: str | None = None
    newPassword: str | None = None
