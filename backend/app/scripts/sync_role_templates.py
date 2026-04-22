from __future__ import annotations

import argparse
import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from app.core.config import get_settings
from app.db.pool import Database
from app.repositories.hr import RoleRepository
from app.scripts.sync_permissions import sync_permissions_for_organizations


CORE_VIEWER_PERMISSION_PREFIXES = ("department", "client", "currency", "poultry_type", "position")
MODULE_ROLE_LABEL_UZ: dict[str, str] = {
    "egg": "Maточnik boshlig'i",
    "incubation": "Inkubatsiya boshlig'i",
    "factory": "Fabrika boshlig'i",
    "feed": "Yem-xashak boshlig'i",
    "medicine": "Vet dorixona boshlig'i",
    "slaughter": "So'yish sexi boshlig'i",
}


@dataclass(frozen=True, slots=True)
class RoleTemplate:
    slug: str
    name: str
    description: str
    permission_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RoleTemplateSyncStats:
    organizations_total: int
    roles_created: int
    roles_updated: int
    role_permission_links_written: int


def _normalize_value(value: object | None) -> str:
    return str(value or "").strip().lower()


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
            # Handle double-encoded JSON: json.loads returned a string instead of a list
            if isinstance(parsed, str):
                try:
                    parsed = json.loads(parsed)
                except Exception:
                    parsed = [parsed]
        except Exception:
            parsed = [candidate]
    elif isinstance(raw_value, (list, tuple, set)):
        parsed = list(raw_value)
    else:
        parsed = [raw_value]

    normalized: set[str] = set()
    for item in parsed:
        value = _normalize_value(item)
        if value:
            normalized.add(value)
    return normalized


def _is_read_only_resource(resource: dict[str, Any]) -> bool:
    resource_key = _normalize_value(resource.get("key"))
    permission_prefix = _normalize_value(resource.get("permission_prefix"))
    return "analytics" in resource_key or permission_prefix.endswith("_analytics")




async def _fetch_organizations(
    db: Database,
    *,
    organization_ids: set[str] | None = None,
) -> list[tuple[str, str]]:
    rows = await db.fetch(
        """
        SELECT id AS organization_id, coalesce(name, '') AS name
        FROM organizations
        ORDER BY name, id
        """
    )
    organizations: list[tuple[str, str]] = []
    for row in rows:
        organization_id = str(row["organization_id"])
        if organization_ids is not None and organization_id not in organization_ids:
            continue
        organizations.append((organization_id, str(row["name"] or "").strip()))
    return organizations


async def _fetch_department_modules(db: Database) -> list[dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT
            key,
            name,
            implicit_read_permissions,
            analytics_read_permissions
        FROM department_modules
        WHERE is_active = true
          AND is_department_assignable = true
        ORDER BY sort_order, name, key
        """
    )
    return [dict(row) for row in rows]


async def _fetch_workspace_resources(db: Database) -> dict[str, list[dict[str, Any]]]:
    # Role templates depend on the full set of configured resources, not
    # on which ones currently surface in the menu. `is_active = false`
    # just hides a resource from the dropdown (e.g. the consolidated
    # shared catalogs live only in core's menu but each module manager
    # still needs warehouse/client/employee access).
    rows = await db.fetch(
        """
        SELECT
            module_key,
            key,
            name,
            permission_prefix
        FROM workspace_resources
        ORDER BY module_key, sort_order, name, key, id
        """
    )
    resources_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        module_key = _normalize_value(row.get("module_key"))
        if not module_key:
            continue
        resources_by_module[module_key].append(dict(row))
    return dict(resources_by_module)


def _build_role_templates(
    modules: list[dict[str, Any]],
    resources_by_module: dict[str, list[dict[str, Any]]],
) -> list[RoleTemplate]:
    templates: list[RoleTemplate] = []

    for module in modules:
        module_key = _normalize_value(module.get("key"))
        all_resources = resources_by_module.get(module_key, [])
        if not module_key or not all_resources:
            continue

        permission_codes: set[str] = set()

        permission_codes.update(
            _parse_permission_collection(module.get("implicit_read_permissions"))
        )
        permission_codes.update(
            _parse_permission_collection(module.get("analytics_read_permissions"))
        )

        for resource in all_resources:
            permission_prefix = _normalize_value(resource.get("permission_prefix"))
            if not permission_prefix:
                continue
            if _is_read_only_resource(resource):
                permission_codes.add(f"{permission_prefix}.read")
            else:
                for action in ("read", "create", "write", "delete"):
                    permission_codes.add(f"{permission_prefix}.{action}")

        for prefix in CORE_VIEWER_PERMISSION_PREFIXES:
            for action in ("read", "create", "write", "delete"):
                permission_codes.add(f"{prefix}.{action}")

        label = MODULE_ROLE_LABEL_UZ.get(module_key, f"{module_key} boshlig'i")
        templates.append(
            RoleTemplate(
                slug=f"{module_key}-manager",
                name=label,
                description=f"Bo'lim boshlig'i — to'liq huquq. Modul: {module_key}.",
                permission_codes=tuple(sorted(permission_codes)),
            )
        )

    return templates


async def _fetch_existing_roles(
    db: Database,
    *,
    organization_ids: set[str] | None,
    slugs: set[str],
) -> dict[tuple[str, str], dict[str, Any]]:
    rows = await db.fetch(
        """
        SELECT
            id,
            organization_id,
            lower(slug) AS slug,
            name,
            description,
            is_active
        FROM roles
        WHERE is_active = true OR is_active = false
        ORDER BY organization_id, slug
        """
    )

    roles_by_org_and_slug: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        organization_id = str(row["organization_id"] or "")
        slug = _normalize_value(row.get("slug"))
        if not organization_id or not slug or slug not in slugs:
            continue
        if organization_ids is not None and organization_id not in organization_ids:
            continue
        roles_by_org_and_slug[(organization_id, slug)] = dict(row)
    return roles_by_org_and_slug


async def _fetch_permission_ids_by_org_and_code(
    db: Database,
    *,
    organization_ids: set[str] | None,
    permission_codes: set[str],
) -> dict[str, dict[str, str]]:
    if not permission_codes:
        return {}

    rows = await db.fetch(
        """
        SELECT id, organization_id, lower(code) AS code
        FROM permissions
        WHERE is_active = true
        ORDER BY organization_id, code
        """
    )

    permissions_by_org: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        organization_id = str(row["organization_id"] or "")
        code = _normalize_value(row.get("code"))
        if not organization_id or not code or code not in permission_codes:
            continue
        if organization_ids is not None and organization_id not in organization_ids:
            continue
        permissions_by_org[organization_id][code] = str(row["id"])
    return dict(permissions_by_org)


async def _upsert_template_role(
    db: Database,
    *,
    organization_id: str,
    template: RoleTemplate,
    existing_role: dict[str, Any] | None,
    dry_run: bool,
) -> tuple[str, bool, bool]:
    if existing_role is None:
        role_id = str(uuid4())
        if not dry_run:
            await db.execute(
                """
                INSERT INTO roles (
                    id,
                    organization_id,
                    name,
                    slug,
                    description,
                    is_active
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                role_id,
                organization_id,
                template.name,
                template.slug,
                template.description,
                True,
            )
        return role_id, True, False

    role_id = str(existing_role["id"])
    needs_update = (
        str(existing_role.get("name") or "") != template.name
        or str(existing_role.get("description") or "") != template.description
        or bool(existing_role.get("is_active")) is not True
    )
    if needs_update and not dry_run:
        await db.execute(
            """
            UPDATE roles
            SET name = $2,
                description = $3,
                is_active = $4
            WHERE id = $1
            """,
            role_id,
            template.name,
            template.description,
            True,
        )
    return role_id, False, needs_update


async def _sync_template_role_permissions(
    repository: RoleRepository,
    *,
    role_id: str,
    permission_ids: Sequence[str],
    dry_run: bool,
) -> int:
    current_map = await repository.get_permission_ids_map([role_id])
    current_permission_ids = tuple(current_map.get(role_id, []))
    target_permission_ids = tuple(sorted(dict.fromkeys(permission_ids)))

    if current_permission_ids == target_permission_ids:
        return 0

    if not dry_run:
        await repository.replace_permissions(role_id, target_permission_ids)
    return len(target_permission_ids)


async def sync_role_templates_for_organizations(
    db: Database,
    *,
    organization_ids: Sequence[str] | None = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> RoleTemplateSyncStats:
    normalized_organization_ids = (
        {
            str(organization_id).strip()
            for organization_id in organization_ids
            if str(organization_id).strip()
        }
        if organization_ids is not None
        else None
    )

    await sync_permissions_for_organizations(
        db,
        organization_ids=tuple(normalized_organization_ids) if normalized_organization_ids else None,
        sync_privileged_roles=False,
        dry_run=dry_run,
        verbose=verbose,
    )

    organizations = await _fetch_organizations(db, organization_ids=normalized_organization_ids)
    modules = await _fetch_department_modules(db)
    resources_by_module = await _fetch_workspace_resources(db)
    templates = _build_role_templates(modules, resources_by_module)
    template_slugs = {template.slug for template in templates}
    permission_codes = {
        permission_code
        for template in templates
        for permission_code in template.permission_codes
    }

    existing_roles = await _fetch_existing_roles(
        db,
        organization_ids=normalized_organization_ids,
        slugs=template_slugs,
    )
    permissions_by_org = await _fetch_permission_ids_by_org_and_code(
        db,
        organization_ids=normalized_organization_ids,
        permission_codes=permission_codes,
    )
    role_repository = RoleRepository(db)

    roles_created = 0
    roles_updated = 0
    role_permission_links_written = 0

    async with db.transaction():
        for organization_id, _organization_name in organizations:
            organization_permission_ids = permissions_by_org.get(organization_id, {})
            for template in templates:
                role_id, created, updated = await _upsert_template_role(
                    db,
                    organization_id=organization_id,
                    template=template,
                    existing_role=existing_roles.get((organization_id, template.slug)),
                    dry_run=dry_run,
                )
                if created:
                    roles_created += 1
                if updated:
                    roles_updated += 1

                permission_ids = [
                    organization_permission_ids[permission_code]
                    for permission_code in template.permission_codes
                    if permission_code in organization_permission_ids
                ]
                role_permission_links_written += await _sync_template_role_permissions(
                    role_repository,
                    role_id=role_id,
                    permission_ids=permission_ids,
                    dry_run=dry_run,
                )

    return RoleTemplateSyncStats(
        organizations_total=len(organizations),
        roles_created=roles_created,
        roles_updated=roles_updated,
        role_permission_links_written=role_permission_links_written,
    )


async def _main(*, dry_run: bool, organization_ids: Sequence[str] | None) -> None:
    settings = get_settings()
    db = Database(
        settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()

    try:
        stats = await sync_role_templates_for_organizations(
            db,
            organization_ids=organization_ids,
            dry_run=dry_run,
            verbose=True,
        )
    finally:
        await db.disconnect()

    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"\nRole template sync mode: {mode}")
    print(f"Organizations processed: {stats.organizations_total}")
    print(f"Roles created: {stats.roles_created}")
    print(f"Roles updated: {stats.roles_updated}")
    print(f"Role-permission sets written: {stats.role_permission_links_written}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Synchronize template roles for operational modules and directories.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview role template changes without writing to DB.",
    )
    parser.add_argument(
        "--organization-id",
        action="append",
        dest="organization_ids",
        help="Limit role template sync to one or more organization ids.",
    )
    args = parser.parse_args()
    asyncio.run(
        _main(
            dry_run=args.dry_run,
            organization_ids=args.organization_ids,
        )
    )


if __name__ == "__main__":
    main()
