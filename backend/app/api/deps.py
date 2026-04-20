from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import get_settings
from app.core.scope import UserScope, load_user_scope
from app.db.pool import Database
from app.db.redis_client import RedisClient
from app.services.auth_access import (
    fetch_auth_profile_data,
)
from app.utils.auth_tokens import TokenError, decode_signed_token, extract_bearer_token


@dataclass(frozen=True)
class CurrentActor:
    """Auth context extracted from headers."""

    employee_id: str
    organization_id: str
    department_id: str | None
    department_module_key: str | None
    username: str
    roles: frozenset[str]
    permissions: frozenset[str]
    implicit_read_permissions: frozenset[str]
    scope: UserScope = UserScope.unbounded()

    @property
    def allowed_department_ids(self) -> frozenset[str] | None:
        return self.scope.allowed_department_ids

    @property
    def allowed_warehouse_ids(self) -> frozenset[str] | None:
        return self.scope.allowed_warehouse_ids

    @property
    def is_org_admin(self) -> bool:
        return self.scope.is_org_admin


def _split_csv(raw: str | None) -> frozenset[str]:
    if not raw:
        return frozenset()
    return frozenset(token.strip().lower() for token in raw.split(",") if token.strip())


async def get_db(request: Request) -> Database:
    return request.app.state.db


async def db_dependency(db: Database = Depends(get_db)) -> Database:
    return db


async def get_current_actor(
    db: Database = Depends(db_dependency),
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_employee_id: str | None = Header(default=None, alias="X-Employee-Id"),
    x_roles: str | None = Header(default=None, alias="X-Roles"),
    x_permissions: str | None = Header(default=None, alias="X-Permissions"),
) -> CurrentActor:
    settings = get_settings()
    bearer_token = extract_bearer_token(authorization)

    if bearer_token:
        try:
            claims = decode_signed_token(
                bearer_token,
                secret_key=settings.auth_secret_key,
                expected_type="access",
            )
        except TokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

        profile = await fetch_auth_profile_data(db, str(claims["sub"]))
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        roles = frozenset(profile.roles)
        scope = await load_user_scope(
            db,
            employee_id=profile.employee_id,
            organization_id=profile.organization_id,
            roles=roles,
            enabled=settings.enable_row_level_scope,
        )
        return CurrentActor(
            employee_id=profile.employee_id,
            organization_id=profile.organization_id,
            department_id=profile.department_id,
            department_module_key=profile.department_module_key,
            username=profile.username,
            roles=roles,
            permissions=frozenset(profile.permissions),
            implicit_read_permissions=frozenset(profile.implicit_read_permissions),
            scope=scope,
        )

    allow_header_override = (
        settings.auth_allow_header_overrides and settings.environment.lower() != "production"
    )
    if allow_header_override and x_employee_id:
        profile = await fetch_auth_profile_data(db, x_employee_id)
        if profile is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        has_claim_overrides = x_roles is not None or x_permissions is not None
        roles = _split_csv(x_roles) or frozenset(profile.roles)
        scope = await load_user_scope(
            db,
            employee_id=profile.employee_id,
            organization_id=profile.organization_id,
            roles=roles,
            enabled=settings.enable_row_level_scope,
        )
        return CurrentActor(
            employee_id=profile.employee_id,
            organization_id=profile.organization_id,
            department_id=profile.department_id,
            department_module_key=(
                None if has_claim_overrides else profile.department_module_key
            ),
            username=profile.username,
            roles=roles,
            permissions=_split_csv(x_permissions) or frozenset(profile.permissions),
            implicit_read_permissions=(
                frozenset()
                if has_claim_overrides
                else frozenset(profile.implicit_read_permissions)
            ),
            scope=scope,
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
    )


def require_access(
    permission: str,
    *,
    roles: Iterable[str] | None = None,
) -> Callable[[CurrentActor], None]:
    allowed_roles = frozenset(role.lower() for role in (roles or ()))

    async def dependency(current: CurrentActor = Depends(get_current_actor)) -> None:
        permission_requested = permission.lower()
        if "admin" in current.roles or "super_admin" in current.roles:
            return
        if permission_requested in current.permissions:
            return
        if (
            permission_requested.endswith(".read")
            and permission_requested in current.implicit_read_permissions
        ):
            return
        if allowed_roles and allowed_roles.intersection(current.roles):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return dependency

async def _employee_heads_any_department(db: Database, employee_id: str) -> bool:
    row = await db.fetchrow(
        """
        SELECT 1
        FROM departments
        WHERE head_id = $1
        LIMIT 1
        """,
        employee_id,
    )
    return row is not None


def require_department_management_access(
    permission: str,
    *,
    roles: Iterable[str] | None = None,
) -> Callable[..., None]:
    base_dependency = require_access(permission, roles=roles)

    async def dependency(
        current: CurrentActor = Depends(get_current_actor),
        db: Database = Depends(db_dependency),
    ) -> None:
        try:
            await base_dependency(current)
            return
        except HTTPException as exc:
            if exc.status_code != status.HTTP_403_FORBIDDEN:
                raise

        if await _employee_heads_any_department(db, current.employee_id):
            return

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )

    return dependency


async def get_redis(request: Request) -> RedisClient:
    return request.app.state.redis


async def redis_dependency(redis: RedisClient = Depends(get_redis)) -> RedisClient:
    return redis
