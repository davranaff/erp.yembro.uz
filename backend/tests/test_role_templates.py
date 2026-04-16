from __future__ import annotations

import pytest

from app.scripts.sync_role_templates import sync_role_templates_for_organizations


PRIMARY_ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"


async def _get_role_permission_codes(sqlite_db, organization_id: str, slug: str) -> set[str]:
    rows = await sqlite_db.fetch(
        """
        SELECT lower(p.code) AS code
        FROM permissions AS p
        INNER JOIN role_permissions AS rp
          ON rp.permission_id = p.id
        INNER JOIN roles AS r
          ON r.id = rp.role_id
        WHERE r.organization_id = $1
          AND lower(r.slug) = $2
        ORDER BY code
        """,
        organization_id,
        slug,
    )
    return {str(row["code"]) for row in rows if row.get("code") is not None}


@pytest.mark.asyncio
async def test_sync_role_templates_creates_core_viewer_and_module_manager_roles(sqlite_db) -> None:
    stats = await sync_role_templates_for_organizations(
        sqlite_db,
        organization_ids=[PRIMARY_ORGANIZATION_ID],
    )

    assert stats.organizations_total == 1

    core_viewer_codes = await _get_role_permission_codes(
        sqlite_db,
        PRIMARY_ORGANIZATION_ID,
        "core-viewer",
    )
    assert {
        "department.read",
        "client.read",
        "currency.read",
        "poultry_type.read",
        "position.read",
    }.issubset(core_viewer_codes)
    assert "role.read" not in core_viewer_codes

    egg_manager_codes = await _get_role_permission_codes(
        sqlite_db,
        PRIMARY_ORGANIZATION_ID,
        "egg-manager",
    )
    assert {
        "egg_production.read",
        "egg_production.delete",
        "egg_shipment.delete",
        "warehouse.read",
        # managers get справочники (core-viewer) permissions
        "department.read",
        "client.read",
        "currency.read",
        "poultry_type.read",
        "position.read",
    }.issubset(egg_manager_codes)
    # general dashboard is admin-only
    assert "dashboard.read" not in egg_manager_codes
