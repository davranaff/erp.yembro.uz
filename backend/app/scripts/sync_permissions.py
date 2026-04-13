from __future__ import annotations

import argparse
import asyncio
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from app.core.config import get_settings
from app.db.pool import Database
from app.scripts.load_fixtures import FIXTURES_DIR, _load_fixture_rows


CRUD_ACTIONS: tuple[str, ...] = ("read", "create", "write", "delete")
PERMISSION_PREFIX_RE = re.compile(r'permission_prefix\s*=\s*["\']([a-zA-Z0-9_.-]+)["\']')
REQUIRE_ACCESS_RE = re.compile(r'require_access\(\s*["\']([a-zA-Z0-9_.-]+)["\']')
FRONTEND_PERMISSION_CODE_RE = re.compile(r'["\']([a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)+)["\']')
PRIVILEGED_ROLE_SLUGS = ("admin", "super_admin", "manager")
SYSTEM_PERMISSION_CODES = {"audit.read", "dashboard.read"}
FRONTEND_FALLBACK_PERMISSION_CODES = {
    "role.read",
    "role.create",
    "role.write",
    "role.delete",
    "employee.read",
    "employee.write",
    "department.read",
    "department.create",
    "department.write",
    "department.delete",
    "audit.read",
    "dashboard.read",
}


@dataclass(slots=True)
class DiscoveryResult:
    api_prefixes: set[str]
    api_explicit_codes: set[str]
    workspace_prefixes: set[str]
    module_codes: set[str]
    fixture_codes: set[str]
    frontend_codes: set[str]

    @property
    def generated_codes(self) -> set[str]:
        prefixes = self.api_prefixes.union(self.workspace_prefixes)
        return {
            f"{prefix}.{action}"
            for prefix in prefixes
            for action in CRUD_ACTIONS
        }

    @property
    def all_codes(self) -> set[str]:
        return (
            self.generated_codes
            .union(self.api_explicit_codes)
            .union(self.module_codes)
            .union(self.fixture_codes)
            .union(self.frontend_codes)
            .union(SYSTEM_PERMISSION_CODES)
        )


@dataclass(slots=True)
class SyncStats:
    organizations_total: int
    permission_codes_total: int
    inserted_total: int
    inserted_by_organization: dict[str, int]
    privileged_roles_total: int
    privileged_role_links_inserted: int
    privileged_role_links_by_role: dict[str, int]


def _normalize_value(value: object | None) -> str:
    return str(value or "").strip().lower()


def _normalize_code(code: str) -> str:
    return _normalize_value(code)


def _build_placeholders(count: int, *, start: int = 1) -> str:
    return ", ".join(f"${index}" for index in range(start, start + count))


def _parse_permission_collection(raw_value: object | None) -> set[str]:
    if raw_value is None:
        return set()

    parsed: object
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return set()
        try:
            parsed = json.loads(candidate)
        except Exception:
            parsed = [candidate]
    elif isinstance(raw_value, (list, tuple, set)):
        parsed = list(raw_value)
    else:
        parsed = [raw_value]

    normalized: set[str] = set()
    for item in parsed:
        code = _normalize_code(str(item))
        if code:
            normalized.add(code)
    return normalized


def _split_resource_action(code: str) -> tuple[str | None, str | None]:
    normalized = _normalize_code(code)
    if "." not in normalized:
        return None, None

    resource, action = normalized.rsplit(".", 1)
    if not resource:
        return None, None
    if not action:
        return resource, None
    return resource, action


def _build_description(code: str, resource: str | None, action: str | None) -> str:
    if resource and action:
        return f"Auto-synced permission: {resource}.{action}"
    return f"Auto-synced permission: {code}"


@lru_cache(maxsize=1)
def _discover_api_permissions() -> tuple[set[str], set[str]]:
    app_dir = Path(__file__).resolve().parents[1]
    api_dir = app_dir / "api"

    prefixes: set[str] = set()
    explicit_codes: set[str] = set()

    for path in sorted(api_dir.rglob("*.py")):
        content = path.read_text(encoding="utf-8")

        for match in PERMISSION_PREFIX_RE.finditer(content):
            prefix = _normalize_value(match.group(1))
            if prefix:
                prefixes.add(prefix)

        for match in REQUIRE_ACCESS_RE.finditer(content):
            code = _normalize_code(match.group(1))
            if code:
                explicit_codes.add(code)

    return prefixes, explicit_codes


@lru_cache(maxsize=1)
def _discover_fixture_permission_codes() -> set[str]:
    rows_by_table = _load_fixture_rows(FIXTURES_DIR)
    permission_rows = rows_by_table.get("permissions", [])
    return {
        _normalize_code(str(row.get("code") or ""))
        for row in permission_rows
        if _normalize_code(str(row.get("code") or ""))
    }


def _resolve_frontend_access_path() -> Path | None:
    # Host setup: <repo>/backend/app/scripts/sync_permissions.py
    host_candidate = Path(__file__).resolve().parents[3] / "frontend" / "src" / "shared" / "auth" / "access.ts"
    if host_candidate.exists():
        return host_candidate

    # API container setup usually mounts only backend as /app.
    container_candidate = Path("/app/frontend/src/shared/auth/access.ts")
    if container_candidate.exists():
        return container_candidate

    return None


@lru_cache(maxsize=1)
def _discover_frontend_permission_codes() -> set[str]:
    frontend_access_path = _resolve_frontend_access_path()
    if frontend_access_path is None:
        return set(FRONTEND_FALLBACK_PERMISSION_CODES)

    content = frontend_access_path.read_text(encoding="utf-8")
    discovered = {
        _normalize_code(match.group(1))
        for match in FRONTEND_PERMISSION_CODE_RE.finditer(content)
        if _normalize_code(match.group(1))
    }
    return discovered.union(FRONTEND_FALLBACK_PERMISSION_CODES)


async def _discover_workspace_prefixes(db: Database) -> set[str]:
    rows = await db.fetch(
        """
        SELECT DISTINCT lower(permission_prefix) AS permission_prefix
        FROM workspace_resources
        WHERE permission_prefix IS NOT NULL
          AND trim(permission_prefix) <> ''
        """,
    )
    return {
        _normalize_value(row["permission_prefix"])
        for row in rows
        if _normalize_value(row["permission_prefix"])
    }


async def _discover_department_module_codes(db: Database) -> set[str]:
    rows = await db.fetch(
        """
        SELECT implicit_read_permissions, analytics_read_permissions
        FROM department_modules
        """
    )

    codes: set[str] = set()
    for row in rows:
        codes.update(_parse_permission_collection(row.get("implicit_read_permissions")))
        codes.update(_parse_permission_collection(row.get("analytics_read_permissions")))
    return codes


async def _discover_permission_sources(db: Database) -> DiscoveryResult:
    api_prefixes, api_explicit_codes = _discover_api_permissions()
    fixture_codes = _discover_fixture_permission_codes()
    frontend_codes = _discover_frontend_permission_codes()
    workspace_prefixes = await _discover_workspace_prefixes(db)
    module_codes = await _discover_department_module_codes(db)

    return DiscoveryResult(
        api_prefixes=api_prefixes,
        api_explicit_codes=api_explicit_codes,
        workspace_prefixes=workspace_prefixes,
        module_codes=module_codes,
        fixture_codes=fixture_codes,
        frontend_codes=frontend_codes,
    )


async def _fetch_organizations(db: Database) -> list[tuple[str, str]]:
    rows = await db.fetch(
        """
        SELECT id AS organization_id, coalesce(name, '') AS name
        FROM organizations
        ORDER BY name, id
        """
    )
    return [(str(row["organization_id"]), str(row["name"])) for row in rows]


async def _fetch_existing_permissions(db: Database) -> dict[str, set[str]]:
    rows = await db.fetch(
        """
        SELECT organization_id AS organization_id, lower(code) AS code
        FROM permissions
        """
    )

    codes_by_org: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        organization_id = _normalize_value(row["organization_id"])
        code = _normalize_code(str(row["code"] or ""))
        if organization_id and code:
            codes_by_org[organization_id].add(code)
    return dict(codes_by_org)


async def _sync_privileged_role_permissions(
    db: Database,
    *,
    target_codes: list[str],
    organization_ids: set[str] | None,
    dry_run: bool,
) -> tuple[int, int, dict[str, int]]:
    role_rows = await db.fetch(
        """
        SELECT
            id AS role_id,
            organization_id AS organization_id,
            lower(slug) AS slug,
            coalesce(name, '') AS name
        FROM roles
        WHERE is_active = true
        ORDER BY organization_id, slug
        """
    )

    filtered_role_rows = []
    allowed_slugs = set(PRIVILEGED_ROLE_SLUGS)
    for row in role_rows:
        role_slug = _normalize_value(row.get("slug"))
        role_organization_id = str(row.get("organization_id") or "")
        if role_slug not in allowed_slugs:
            continue
        if organization_ids is not None and role_organization_id not in organization_ids:
            continue
        filtered_role_rows.append(row)

    if not filtered_role_rows or not target_codes:
        return 0, 0, {}

    links_inserted_total = 0
    links_by_role: dict[str, int] = {}

    code_placeholders = _build_placeholders(len(target_codes), start=3)
    count_query = """
        SELECT count(*)::int AS missing_count
        FROM permissions p
        LEFT JOIN role_permissions rp
          ON rp.role_id = $1
         AND rp.permission_id = p.id
        WHERE p.organization_id = $2
          AND p.is_active = true
          AND lower(p.code) IN ({code_placeholders})
          AND rp.role_id IS NULL
    """.format(code_placeholders=code_placeholders)

    insert_query = """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT $1::uuid, p.id
        FROM permissions p
        LEFT JOIN role_permissions rp
          ON rp.role_id = $1
         AND rp.permission_id = p.id
        WHERE p.organization_id = $2
          AND p.is_active = true
          AND lower(p.code) IN ({code_placeholders})
          AND rp.role_id IS NULL
        RETURNING permission_id
    """.format(code_placeholders=code_placeholders)

    for row in filtered_role_rows:
        role_id = str(row["role_id"])
        organization_id = str(row["organization_id"])
        role_slug = _normalize_value(row["slug"])
        role_name = str(row["name"] or "").strip() or role_slug
        role_label = f"{role_name} [{role_slug}] @ {organization_id}"
        query_args = (role_id, organization_id, *target_codes)

        if dry_run:
            missing_row = await db.fetchrow(count_query, *query_args)
            inserted_for_role = int(missing_row["missing_count"] if missing_row is not None else 0)
        else:
            inserted_rows = await db.fetch(insert_query, *query_args)
            inserted_for_role = len(inserted_rows)

        links_by_role[role_label] = inserted_for_role
        links_inserted_total += inserted_for_role

    return len(filtered_role_rows), links_inserted_total, links_by_role


async def _sync_permissions(
    db: Database,
    *,
    organization_ids: Sequence[str] | None,
    dry_run: bool,
    sync_privileged_roles: bool,
    verbose: bool,
) -> SyncStats:
    discovery = await _discover_permission_sources(db)
    target_codes = sorted(discovery.all_codes)
    normalized_organization_ids = (
        {
            _normalize_value(organization_id)
            for organization_id in organization_ids
            if _normalize_value(organization_id)
        }
        if organization_ids is not None
        else None
    )
    organizations = [
        organization
        for organization in await _fetch_organizations(db)
        if normalized_organization_ids is None or _normalize_value(organization[0]) in normalized_organization_ids
    ]
    existing_by_org = await _fetch_existing_permissions(db)

    if verbose:
        print(f"API permission prefixes found: {len(discovery.api_prefixes)}")
        print(f"Workspace permission prefixes found: {len(discovery.workspace_prefixes)}")
        print(f"Explicit permission codes found: {len(discovery.api_explicit_codes)}")
        print(f"Fixture permission codes found: {len(discovery.fixture_codes)}")
        print(f"Frontend explicit permission codes found: {len(discovery.frontend_codes)}")
        print(f"Department-module codes found: {len(discovery.module_codes)}")
        print(f"Total unique target permission codes: {len(target_codes)}")
        print(f"Organizations found: {len(organizations)}")

    inserted_total = 0
    inserted_by_org: dict[str, int] = {}
    privileged_roles_total = 0
    privileged_role_links_inserted = 0
    privileged_role_links_by_role: dict[str, int] = {}

    if not organizations:
        return SyncStats(
            organizations_total=0,
            permission_codes_total=len(target_codes),
            inserted_total=0,
            inserted_by_organization={},
            privileged_roles_total=0,
            privileged_role_links_inserted=0,
            privileged_role_links_by_role={},
        )

    async with db.transaction():
        for organization_id, organization_name in organizations:
            existing_codes = existing_by_org.get(_normalize_value(organization_id), set())
            inserted_for_org = 0

            for code in target_codes:
                if code in existing_codes:
                    continue

                resource, action = _split_resource_action(code)
                description = _build_description(code, resource, action)

                if not dry_run:
                    await db.execute(
                        """
                        INSERT INTO permissions (
                            id,
                            organization_id,
                            code,
                            resource,
                            action,
                            description,
                            is_active
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (organization_id, code) DO NOTHING
                        """,
                        str(uuid4()),
                        organization_id,
                        code,
                        resource,
                        action,
                        description,
                        True,
                    )

                inserted_for_org += 1

            inserted_by_org[organization_name or organization_id] = inserted_for_org
            inserted_total += inserted_for_org

        if sync_privileged_roles:
            (
                privileged_roles_total,
                privileged_role_links_inserted,
                privileged_role_links_by_role,
            ) = await _sync_privileged_role_permissions(
                db,
                target_codes=target_codes,
                organization_ids=normalized_organization_ids,
                dry_run=dry_run,
            )

    return SyncStats(
        organizations_total=len(organizations),
        permission_codes_total=len(target_codes),
        inserted_total=inserted_total,
        inserted_by_organization=inserted_by_org,
        privileged_roles_total=privileged_roles_total,
        privileged_role_links_inserted=privileged_role_links_inserted,
        privileged_role_links_by_role=privileged_role_links_by_role,
    )


def _print_stats(stats: SyncStats, *, dry_run: bool) -> None:
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\nPermission sync mode: {mode}")
    print(f"Organizations processed: {stats.organizations_total}")
    print(f"Permission codes considered: {stats.permission_codes_total}")
    print(f"Permissions to insert{' (estimated)' if dry_run else ''}: {stats.inserted_total}")

    for organization_name, inserted_count in stats.inserted_by_organization.items():
        print(f" - {organization_name}: {inserted_count}")

    print(f"Privileged roles processed: {stats.privileged_roles_total}")
    print(
        "Privileged role-permission links to insert"
        f"{' (estimated)' if dry_run else ''}: {stats.privileged_role_links_inserted}"
    )
    for role_label, inserted_count in stats.privileged_role_links_by_role.items():
        print(f" - {role_label}: {inserted_count}")


async def _main(*, dry_run: bool, sync_privileged_roles: bool, fail_on_diff: bool) -> None:
    settings = get_settings()
    db = Database(
        settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()

    try:
        stats = await _sync_permissions(
            db,
            organization_ids=None,
            dry_run=dry_run,
            sync_privileged_roles=sync_privileged_roles,
            verbose=True,
        )
    finally:
        await db.disconnect()

    _print_stats(stats, dry_run=dry_run)
    if fail_on_diff and (
        stats.inserted_total > 0 or stats.privileged_role_links_inserted > 0
    ):
        raise SystemExit(1)


async def sync_permissions_for_organizations(
    db: Database,
    *,
    organization_ids: Sequence[str] | None = None,
    sync_privileged_roles: bool = False,
    dry_run: bool = False,
    verbose: bool = False,
) -> SyncStats:
    return await _sync_permissions(
        db,
        organization_ids=organization_ids,
        dry_run=dry_run,
        sync_privileged_roles=sync_privileged_roles,
        verbose=verbose,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize permissions table from project permission sources.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print how many permissions would be inserted without writing to DB.",
    )
    parser.add_argument(
        "--skip-privileged-roles",
        action="store_true",
        help="Skip syncing role_permissions for privileged role slugs (admin/super_admin/manager).",
    )
    parser.add_argument(
        "--fail-on-diff",
        action="store_true",
        help="Exit with status 1 if sync would insert missing permissions or role-permission links.",
    )
    args = parser.parse_args()
    asyncio.run(
        _main(
            dry_run=args.dry_run,
            sync_privileged_roles=not args.skip_privileged_roles,
            fail_on_diff=args.fail_on_diff,
        )
    )


if __name__ == "__main__":
    main()
