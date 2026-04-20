from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import CurrentActor, db_dependency, get_current_actor
from app.core.config import get_settings
from app.db.pool import Database
from app.repositories.hr import EmployeeRepository
from app.schemas.auth import (
    AuthLoginRequestSchema,
    AuthLoginResponseSchema,
    AuthProfileSchema,
    AuthRefreshRequestSchema,
    AuthProfileUpdateSchema,
)
from app.core.scope import UserScope, load_user_scope
from app.services.auth_access import AuthProfileData, fetch_auth_profile_data
from app.services.hr import EmployeeService
from app.utils.auth_tokens import TokenError, create_signed_token, decode_signed_token
from app.utils.password import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _scope_to_schema_fields(scope: UserScope | None) -> dict[str, object]:
    if scope is None:
        return {
            "allowedDepartmentIds": None,
            "allowedWarehouseIds": None,
            "isOrgAdmin": False,
        }
    return {
        "allowedDepartmentIds": (
            sorted(scope.allowed_department_ids)
            if scope.allowed_department_ids is not None
            else None
        ),
        "allowedWarehouseIds": (
            sorted(scope.allowed_warehouse_ids)
            if scope.allowed_warehouse_ids is not None
            else None
        ),
        "isOrgAdmin": scope.is_org_admin,
    }


def _profile_to_schema(
    profile: AuthProfileData,
    *,
    scope: UserScope | None = None,
) -> AuthProfileSchema:
    return AuthProfileSchema(
        employeeId=profile.employee_id,
        organizationId=profile.organization_id,
        departmentId=profile.department_id,
        departmentModuleKey=profile.department_module_key,
        headsAnyDepartment=profile.heads_any_department,
        username=profile.username,
        firstName=profile.first_name,
        lastName=profile.last_name,
        email=profile.email,
        phone=profile.phone,
        roles=list(profile.roles),
        permissions=list(profile.permissions),
        **_scope_to_schema_fields(scope),
    )


def _profile_to_login_response(
    profile: AuthProfileData,
    *,
    access_token: str,
    refresh_token: str,
    expires_at: str,
    scope: UserScope | None = None,
) -> AuthLoginResponseSchema:
    return AuthLoginResponseSchema(
        employeeId=profile.employee_id,
        organizationId=profile.organization_id,
        departmentId=profile.department_id,
        departmentModuleKey=profile.department_module_key,
        headsAnyDepartment=profile.heads_any_department,
        username=profile.username,
        roles=list(profile.roles),
        permissions=list(profile.permissions),
        accessToken=access_token,
        refreshToken=refresh_token,
        expiresAt=expires_at,
        **_scope_to_schema_fields(scope),
    )


async def _load_profile_scope(db: Database, profile: AuthProfileData) -> UserScope:
    settings = get_settings()
    return await load_user_scope(
        db,
        employee_id=profile.employee_id,
        organization_id=profile.organization_id,
        roles=frozenset(profile.roles),
        enabled=settings.enable_row_level_scope,
    )


def _issue_token_pair(employee_id: str) -> tuple[str, str, str]:
    settings = get_settings()
    access_token, access_expires_at = create_signed_token(
        subject=employee_id,
        token_type="access",
        secret_key=settings.auth_secret_key,
        expires_in=timedelta(minutes=settings.auth_access_token_ttl_minutes),
    )
    refresh_token, _ = create_signed_token(
        subject=employee_id,
        token_type="refresh",
        secret_key=settings.auth_secret_key,
        expires_in=timedelta(days=settings.auth_refresh_token_ttl_days),
    )
    return access_token, refresh_token, access_expires_at.isoformat()


@router.post("/login", status_code=status.HTTP_200_OK, response_model=AuthLoginResponseSchema)
async def login(payload: AuthLoginRequestSchema, db: Database = Depends(db_dependency)) -> AuthLoginResponseSchema:
    username = payload.username.strip()
    employee = await db.fetchrow(
        """
        SELECT
            e.id AS id,
            e.password
        FROM employees e
        WHERE lower(e.organization_key) = lower($1)
          AND e.is_active = true
        LIMIT 1
        """,
        username,
    )

    if employee is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not verify_password(payload.password, str(employee["password"])):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    employee_id = str(employee["id"])
    profile = await fetch_auth_profile_data(db, employee_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    access_token, refresh_token, expires_at = _issue_token_pair(employee_id)
    scope = await _load_profile_scope(db, profile)
    return _profile_to_login_response(
        profile,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scope=scope,
    )


@router.post("/refresh", status_code=status.HTTP_200_OK, response_model=AuthLoginResponseSchema)
async def refresh_session(
    payload: AuthRefreshRequestSchema,
    db: Database = Depends(db_dependency),
) -> AuthLoginResponseSchema:
    settings = get_settings()
    try:
        claims = decode_signed_token(
            payload.refreshToken.strip(),
            secret_key=settings.auth_secret_key,
            expected_type="refresh",
        )
    except TokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    employee_id = str(claims["sub"])
    profile = await fetch_auth_profile_data(db, employee_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    access_token, refresh_token, expires_at = _issue_token_pair(employee_id)
    scope = await _load_profile_scope(db, profile)
    return _profile_to_login_response(
        profile,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=expires_at,
        scope=scope,
    )


@router.get("/me", status_code=status.HTTP_200_OK, response_model=AuthProfileSchema)
async def get_me(
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> AuthProfileSchema:
    profile = await fetch_auth_profile_data(db, current_actor.employee_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _profile_to_schema(profile, scope=current_actor.scope)


@router.patch("/me", status_code=status.HTTP_200_OK, response_model=AuthProfileSchema)
async def update_me(
    payload: AuthProfileUpdateSchema,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> AuthProfileSchema:
    employee = await db.fetchrow(
        """
        SELECT id, password
        FROM employees
        WHERE id = $1
          AND is_active = true
        LIMIT 1
        """,
        current_actor.employee_id,
    )

    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")

    update_payload = {
        "first_name": payload.firstName.strip(),
        "last_name": payload.lastName.strip(),
        "email": payload.email.strip() if payload.email is not None and payload.email.strip() else None,
        "phone": payload.phone.strip() if payload.phone is not None and payload.phone.strip() else None,
    }
    current_password = payload.currentPassword.strip() if payload.currentPassword else ""
    new_password = payload.newPassword.strip() if payload.newPassword else ""

    if current_password or new_password:
        if not current_password or not new_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password and new password are required",
            )

        if not verify_password(current_password, str(employee["password"])):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is invalid",
            )

        update_payload["password"] = new_password

    service = EmployeeService(EmployeeRepository(db))
    result = await service.update(current_actor.employee_id, update_payload, actor=current_actor)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Failed to update profile",
        )

    profile = await fetch_auth_profile_data(db, current_actor.employee_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return _profile_to_schema(profile, scope=current_actor.scope)
