from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.hr import EmployeeRepository, PermissionRepository, PositionRepository, RoleRepository
from app.services.hr import EmployeeService, PermissionService, PositionService, RoleService


router = APIRouter(prefix="/hr", tags=["hr"])

router.include_router(
    build_crud_router(
        prefix="employees",
        service_factory=lambda db: EmployeeService(EmployeeRepository(db)),
        permission_prefix="employee",
        tags=["employee"],
    )
)

router.include_router(
    build_crud_router(
        prefix="positions",
        service_factory=lambda db: PositionService(PositionRepository(db)),
        permission_prefix="position",
        tags=["position"],
    )
)

router.include_router(
    build_crud_router(
        prefix="roles",
        service_factory=lambda db: RoleService(RoleRepository(db)),
        permission_prefix="role",
        tags=["role"],
    )
)

router.include_router(
    build_crud_router(
        prefix="permissions",
        service_factory=lambda db: PermissionService(PermissionRepository(db)),
        permission_prefix="permission",
        tags=["permission"],
    )
)

register_module_stats_route(
    router,
    module="hr",
    label="HR",
    tables=(
        ModuleStatsTable(key="employees", label="Employees", table="employees"),
        ModuleStatsTable(key="positions", label="Positions", table="positions"),
        ModuleStatsTable(key="roles", label="Roles", table="roles"),
        ModuleStatsTable(key="permissions", label="Permissions", table="permissions"),
    ),
)

__all__ = ["router"]
