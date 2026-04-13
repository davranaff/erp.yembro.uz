from __future__ import annotations

from dataclasses import dataclass
from json import loads as json_loads

from app.db.pool import Database

@dataclass(frozen=True, slots=True)
class AuthProfileData:
    employee_id: str
    organization_id: str
    department_id: str | None
    department_module_key: str | None
    heads_any_department: bool
    username: str
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    roles: tuple[str, ...]
    permissions: tuple[str, ...]
    implicit_read_permissions: tuple[str, ...]


def _normalize_permission_list(raw_value: object | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return ()
        try:
            parsed = json_loads(candidate)
        except Exception:
            parsed = [candidate]
    elif isinstance(raw_value, (list, tuple, set)):
        parsed = list(raw_value)
    else:
        parsed = [raw_value]

    normalized: list[str] = []
    for item in parsed:
        value = str(item).strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


async def fetch_roles_and_permissions(db: Database, employee_id: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    roles = tuple(
        row["role"]
        for row in await db.fetch(
            """
            SELECT DISTINCT lower(r.slug) AS role
            FROM roles r
            INNER JOIN employee_roles er ON er.role_id = r.id
            WHERE er.employee_id = $1
              AND r.is_active = true
            ORDER BY role
            """,
            employee_id,
        )
        if row["role"] is not None
    )

    permissions = tuple(
        row["permission"]
        for row in await db.fetch(
            """
            SELECT DISTINCT lower(p.code) AS permission
            FROM permissions p
            INNER JOIN role_permissions rp ON rp.permission_id = p.id
            INNER JOIN employee_roles er ON rp.role_id = er.role_id
            INNER JOIN roles r ON r.id = er.role_id
            WHERE er.employee_id = $1
              AND r.is_active = true
              AND p.is_active = true
            ORDER BY permission
            """,
            employee_id,
        )
        if row["permission"] is not None
    )

    return roles, permissions


async def fetch_auth_profile_data(db: Database, employee_id: str) -> AuthProfileData | None:
    employee = await db.fetchrow(
        """
        SELECT
            e.id AS employee_id,
            e.organization_id AS organization_id,
            e.department_id AS department_id,
            d.module_key AS department_module_key,
            dm.implicit_read_permissions AS implicit_read_permissions,
            EXISTS(
                SELECT 1
                FROM departments d
                WHERE d.head_id = e.id
                  AND d.is_active = true
                LIMIT 1
            ) AS heads_any_department,
            e.organization_key,
            e.first_name,
            e.last_name,
            e.email,
            e.phone
        FROM employees e
        LEFT JOIN departments d
          ON d.id = e.department_id
        LEFT JOIN department_modules dm
          ON dm.key = d.module_key
        WHERE e.id = $1
          AND e.is_active = true
        LIMIT 1
        """,
        employee_id,
    )

    if employee is None:
        return None

    roles, permissions = await fetch_roles_and_permissions(db, employee_id)
    return AuthProfileData(
        employee_id=str(employee["employee_id"]),
        organization_id=str(employee["organization_id"]),
        department_id=str(employee["department_id"]) if employee["department_id"] is not None else None,
        department_module_key=(
            str(employee["department_module_key"])
            if employee["department_module_key"] is not None
            else None
        ),
        heads_any_department=bool(employee["heads_any_department"]),
        username=str(employee["organization_key"]),
        first_name=str(employee["first_name"] or ""),
        last_name=str(employee["last_name"] or ""),
        email=str(employee["email"]) if employee["email"] is not None else None,
        phone=str(employee["phone"]) if employee["phone"] is not None else None,
        roles=roles,
        permissions=permissions,
        implicit_read_permissions=_normalize_permission_list(employee.get("implicit_read_permissions")),
    )
