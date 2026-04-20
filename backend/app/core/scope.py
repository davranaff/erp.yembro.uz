"""Row-level scope isolation.

See docs/adr/0001-row-level-scope.md.

`UserScope` is the single entry point for deciding which rows a user may see.
When ``is_org_admin`` is ``True`` (or both allow-lists are ``None``), the scope
is "unbounded" — callers must treat filters as pass-through.

The module is deliberately DB-shape agnostic: it works with filter dicts
consumed by ``app.repositories.base.BaseRepository._where`` (which already
translates list values into SQL ``IN`` clauses).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.db.pool import Database

ORG_ADMIN_ROLES: frozenset[str] = frozenset({"super_admin", "admin"})


@dataclass(frozen=True, slots=True)
class UserScope:
    """Effective row-level scope for a user within an organization.

    Fields are ``None`` when the scope is unbounded for that axis
    (e.g. org admin sees every department).
    """

    allowed_department_ids: frozenset[str] | None
    allowed_warehouse_ids: frozenset[str] | None
    is_org_admin: bool

    @classmethod
    def unbounded(cls) -> "UserScope":
        return cls(
            allowed_department_ids=None,
            allowed_warehouse_ids=None,
            is_org_admin=True,
        )

    def can_access(
        self,
        *,
        department_id: str | None = None,
        warehouse_id: str | None = None,
    ) -> bool:
        if self.is_org_admin:
            return True
        if department_id is not None and self.allowed_department_ids is not None:
            if str(department_id) not in self.allowed_department_ids:
                return False
        if warehouse_id is not None and self.allowed_warehouse_ids is not None:
            if str(warehouse_id) not in self.allowed_warehouse_ids:
                return False
        return True

    def apply_filters(
        self,
        filters: Mapping[str, Any] | None,
        *,
        has_department_column: bool,
        has_warehouse_column: bool,
    ) -> dict[str, Any]:
        """Merge scope allow-lists into a repository filter dict.

        Intersects with any existing value for ``department_id`` /
        ``warehouse_id`` so an explicit user-supplied filter cannot widen scope.
        Empty intersection results in ``[]`` which the repository turns into
        ``1 = 0`` — i.e. the list endpoint returns zero rows.
        """
        merged: dict[str, Any] = dict(filters or {})
        if self.is_org_admin:
            return merged

        if has_department_column and self.allowed_department_ids is not None:
            merged["department_id"] = _intersect(
                merged.get("department_id"), self.allowed_department_ids
            )
        if has_warehouse_column and self.allowed_warehouse_ids is not None:
            merged["warehouse_id"] = _intersect(
                merged.get("warehouse_id"), self.allowed_warehouse_ids
            )
        return merged


def _intersect(existing: Any, allowed: frozenset[str]) -> list[str]:
    if existing is None:
        return list(allowed)
    if isinstance(existing, (list, tuple, set, frozenset)):
        candidates = [str(item) for item in existing if item is not None]
    else:
        candidates = [str(existing)]
    return [value for value in candidates if value in allowed]


async def load_user_scope(
    db: Database,
    *,
    employee_id: str,
    organization_id: str,
    roles: frozenset[str],
    enabled: bool,
) -> UserScope:
    """Compute the effective scope for the given employee.

    ``enabled=False`` returns an unbounded scope — the feature flag path
    preserves existing (single-department) behavior handled elsewhere.
    """
    if not enabled:
        return UserScope.unbounded()

    if roles & ORG_ADMIN_ROLES:
        return UserScope.unbounded()

    # Direct grants from user_scope_assignments.
    grant_rows = await db.fetch(
        """
        SELECT scope_type, scope_id
        FROM user_scope_assignments
        WHERE employee_id = $1
          AND organization_id = $2
          AND permission_prefix IS NULL
        """,
        employee_id,
        organization_id,
    )
    granted_departments: set[str] = set()
    granted_warehouses: set[str] = set()
    for row in grant_rows:
        scope_type = row["scope_type"]
        scope_id = str(row["scope_id"])
        if scope_type == "department":
            granted_departments.add(scope_id)
        elif scope_type == "warehouse":
            granted_warehouses.add(scope_id)

    # Home department (seed) + assignments, then expand by tree.
    home_row = await db.fetchrow(
        """
        SELECT department_id
        FROM employees
        WHERE id = $1
        """,
        employee_id,
    )
    if home_row is not None and home_row["department_id"] is not None:
        granted_departments.add(str(home_row["department_id"]))

    # Department heads: all departments where head_id = employee_id.
    head_rows = await db.fetch(
        """
        SELECT id FROM departments
        WHERE head_id = $1
          AND organization_id = $2
          AND is_active = true
        """,
        employee_id,
        organization_id,
    )
    for row in head_rows:
        granted_departments.add(str(row["id"]))

    # Hierarchical expansion: include all descendants of granted departments.
    if granted_departments:
        expanded_rows = await db.fetch(
            """
            WITH RECURSIVE tree AS (
                SELECT id, parent_department_id
                FROM departments
                WHERE organization_id = $1
                  AND id = ANY($2::uuid[])
                UNION
                SELECT d.id, d.parent_department_id
                FROM departments d
                INNER JOIN tree t ON d.parent_department_id = t.id
                WHERE d.organization_id = $1
            )
            SELECT id FROM tree
            """,
            organization_id,
            list(granted_departments),
        )
        for row in expanded_rows:
            granted_departments.add(str(row["id"]))

    # Warehouses inherit from granted departments.
    inherited_warehouses: set[str] = set()
    if granted_departments:
        wh_rows = await db.fetch(
            """
            SELECT id FROM warehouses
            WHERE organization_id = $1
              AND department_id = ANY($2::uuid[])
            """,
            organization_id,
            list(granted_departments),
        )
        for row in wh_rows:
            inherited_warehouses.add(str(row["id"]))

    allowed_warehouses = inherited_warehouses | granted_warehouses

    return UserScope(
        allowed_department_ids=frozenset(granted_departments),
        allowed_warehouse_ids=frozenset(allowed_warehouses),
        is_org_admin=False,
    )
