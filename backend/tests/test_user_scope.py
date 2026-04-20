from __future__ import annotations

from typing import Any

import pytest

from app.core.scope import UserScope, load_user_scope


# ---------------------------------------------------------------------------
# UserScope dataclass — pure-Python unit tests
# ---------------------------------------------------------------------------


def test_unbounded_scope_is_org_admin() -> None:
    scope = UserScope.unbounded()
    assert scope.is_org_admin is True
    assert scope.allowed_department_ids is None
    assert scope.allowed_warehouse_ids is None


def test_can_access_unbounded_allows_any_department_and_warehouse() -> None:
    scope = UserScope.unbounded()
    assert scope.can_access(department_id="dept-a") is True
    assert scope.can_access(warehouse_id="wh-a") is True
    assert scope.can_access(department_id="x", warehouse_id="y") is True


def test_can_access_bounded_rejects_foreign_department() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a"}),
        allowed_warehouse_ids=frozenset({"wh-a"}),
        is_org_admin=False,
    )
    assert scope.can_access(department_id="dept-a") is True
    assert scope.can_access(department_id="dept-b") is False


def test_can_access_bounded_rejects_foreign_warehouse() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a"}),
        allowed_warehouse_ids=frozenset({"wh-a"}),
        is_org_admin=False,
    )
    assert scope.can_access(warehouse_id="wh-a") is True
    assert scope.can_access(warehouse_id="wh-b") is False


def test_can_access_ignores_axis_when_allow_list_is_none() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a"}),
        allowed_warehouse_ids=None,
        is_org_admin=False,
    )
    assert scope.can_access(warehouse_id="wh-anything") is True


def test_apply_filters_unbounded_is_pass_through() -> None:
    scope = UserScope.unbounded()
    result = scope.apply_filters(
        {"organization_id": "org-1"},
        has_department_column=True,
        has_warehouse_column=True,
    )
    assert result == {"organization_id": "org-1"}


def test_apply_filters_injects_allowed_departments_and_warehouses() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a", "dept-b"}),
        allowed_warehouse_ids=frozenset({"wh-1"}),
        is_org_admin=False,
    )
    result = scope.apply_filters(
        {"organization_id": "org-1"},
        has_department_column=True,
        has_warehouse_column=True,
    )
    assert result["organization_id"] == "org-1"
    assert set(result["department_id"]) == {"dept-a", "dept-b"}
    assert set(result["warehouse_id"]) == {"wh-1"}


def test_apply_filters_intersects_with_user_supplied_department_filter() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a", "dept-b"}),
        allowed_warehouse_ids=None,
        is_org_admin=False,
    )
    # User tried to filter dept-c (outside scope) — must be dropped.
    result = scope.apply_filters(
        {"department_id": ["dept-b", "dept-c"]},
        has_department_column=True,
        has_warehouse_column=False,
    )
    assert set(result["department_id"]) == {"dept-b"}


def test_apply_filters_empty_intersection_yields_empty_list() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a"}),
        allowed_warehouse_ids=None,
        is_org_admin=False,
    )
    result = scope.apply_filters(
        {"department_id": "dept-foreign"},
        has_department_column=True,
        has_warehouse_column=False,
    )
    # Empty list — repository treats as 1=0 (no rows).
    assert result["department_id"] == []


def test_apply_filters_respects_column_availability() -> None:
    scope = UserScope(
        allowed_department_ids=frozenset({"dept-a"}),
        allowed_warehouse_ids=frozenset({"wh-1"}),
        is_org_admin=False,
    )
    result = scope.apply_filters(
        None,
        has_department_column=False,
        has_warehouse_column=True,
    )
    assert "department_id" not in result
    assert set(result["warehouse_id"]) == {"wh-1"}


# ---------------------------------------------------------------------------
# load_user_scope — integration with SQLite test DB
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_load_user_scope_returns_unbounded_when_flag_disabled(
    sqlite_db: Any,
) -> None:
    scope = await load_user_scope(
        sqlite_db,
        employee_id="00000000-0000-0000-0000-000000000000",
        organization_id="00000000-0000-0000-0000-000000000000",
        roles=frozenset({"worker"}),
        enabled=False,
    )
    assert scope.is_org_admin is True
    assert scope.allowed_department_ids is None
    assert scope.allowed_warehouse_ids is None


@pytest.mark.asyncio
async def test_load_user_scope_returns_unbounded_for_admin_role(
    sqlite_db: Any,
) -> None:
    scope = await load_user_scope(
        sqlite_db,
        employee_id="00000000-0000-0000-0000-000000000000",
        organization_id="00000000-0000-0000-0000-000000000000",
        roles=frozenset({"admin"}),
        enabled=True,
    )
    assert scope.is_org_admin is True


@pytest.mark.asyncio
async def test_load_user_scope_returns_unbounded_for_super_admin_role(
    sqlite_db: Any,
) -> None:
    scope = await load_user_scope(
        sqlite_db,
        employee_id="00000000-0000-0000-0000-000000000000",
        organization_id="00000000-0000-0000-0000-000000000000",
        roles=frozenset({"super_admin"}),
        enabled=True,
    )
    assert scope.is_org_admin is True
