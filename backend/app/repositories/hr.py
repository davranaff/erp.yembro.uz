from __future__ import annotations

from typing import Any, Sequence

from app.repositories.base import BaseRepository


def _placeholders(values: Sequence[Any], *, start: int = 1) -> str:
    return ", ".join(f"${index}" for index in range(start, start + len(values)))


class EmployeeRepository(BaseRepository[dict[str, object]]):
    table = "employees"

    async def get_role_ids_map(self, employee_ids: Sequence[Any]) -> dict[str, list[str]]:
        if not employee_ids:
            return {}

        rows = await self.db.fetch(
            (
                "SELECT employee_id, role_id "
                f"FROM employee_roles WHERE employee_id IN ({_placeholders(employee_ids)}) "
                "ORDER BY employee_id, role_id"
            ),
            *employee_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            employee_id = str(row["employee_id"])
            grouped.setdefault(employee_id, []).append(str(row["role_id"]))
        return grouped

    async def get_role_rows(self, role_ids: Sequence[Any]) -> list[dict[str, object]]:
        if not role_ids:
            return []
        rows = await self.db.fetch(
            (
                "SELECT id, organization_id, is_active "
                f"FROM roles WHERE id IN ({_placeholders(role_ids)})"
            ),
            *role_ids,
        )
        return [dict(row) for row in rows]

    async def replace_roles(self, employee_id: Any, role_ids: Sequence[Any]) -> None:
        await self.db.execute("DELETE FROM employee_roles WHERE employee_id = $1", employee_id)
        for role_id in role_ids:
            await self.db.execute(
                "INSERT INTO employee_roles (employee_id, role_id) VALUES ($1, $2)",
                employee_id,
                role_id,
            )


class PositionRepository(BaseRepository[dict[str, object]]):
    table = "positions"


class RoleRepository(BaseRepository[dict[str, object]]):
    table = "roles"

    async def get_permission_ids_map(self, role_ids: Sequence[Any]) -> dict[str, list[str]]:
        if not role_ids:
            return {}

        rows = await self.db.fetch(
            (
                "SELECT role_id, permission_id "
                f"FROM role_permissions WHERE role_id IN ({_placeholders(role_ids)}) "
                "ORDER BY role_id, permission_id"
            ),
            *role_ids,
        )
        grouped: dict[str, list[str]] = {}
        for row in rows:
            role_id = str(row["role_id"])
            grouped.setdefault(role_id, []).append(str(row["permission_id"]))
        return grouped

    async def get_permission_rows(self, permission_ids: Sequence[Any]) -> list[dict[str, object]]:
        if not permission_ids:
            return []
        rows = await self.db.fetch(
            (
                "SELECT id, organization_id, is_active "
                f"FROM permissions WHERE id IN ({_placeholders(permission_ids)})"
            ),
            *permission_ids,
        )
        return [dict(row) for row in rows]

    async def replace_permissions(self, role_id: Any, permission_ids: Sequence[Any]) -> None:
        await self.db.execute("DELETE FROM role_permissions WHERE role_id = $1", role_id)
        for permission_id in permission_ids:
            await self.db.execute(
                "INSERT INTO role_permissions (role_id, permission_id) VALUES ($1, $2)",
                role_id,
                permission_id,
            )


class PermissionRepository(BaseRepository[dict[str, object]]):
    table = "permissions"


__all__ = [
    "EmployeeRepository",
    "PositionRepository",
    "RoleRepository",
    "PermissionRepository",
]
