from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from json import loads as json_loads
from typing import TYPE_CHECKING, Any
import re

from app.core.exceptions import AccessDeniedError, ValidationError
from app.repositories.core import (
    ClientDebtRepository,
    ClientRepository,
    CurrencyRepository,
    DepartmentRepository,
    DepartmentModuleRepository,
    ClientCategoryRepository,
    MeasurementUnitRepository,
    OrganizationRepository,
    PoultryTypeRepository,
    WarehouseRepository,
    WorkspaceResourceRepository,
)
from app.schemas.core import (
    ClientDebtReadSchema,
    ClientReadSchema,
    CurrencyReadSchema,
    DepartmentReadSchema,
    DepartmentModuleReadSchema,
    ClientCategoryReadSchema,
    MeasurementUnitReadSchema,
    OrganizationReadSchema,
    PoultryTypeReadSchema,
    WarehouseReadSchema,
    WorkspaceModuleMetaSchema,
)
from app.scripts.sync_permissions import sync_permissions_for_organizations
from app.services.base import BaseService
from app.services.inventory import (
    ITEM_KEY_REFERENCE_TABLE,
    ITEM_TYPES,
    _fetch_inventory_item_key_options,
    _inventory_item_key_exists,
    normalize_stock_movement_unit,
)
from app.utils.result import Result

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


WAREHOUSE_CODE_SANITIZER_RE = re.compile(r"[^A-Z0-9]+")
CLIENT_DEBT_STATUSES = ("open", "partially_paid", "closed", "cancelled")
HIDDEN_WORKSPACE_MODULE_KEYS = frozenset({"finance"})
WORKSPACE_RESOURCE_READ_PRIVILEGED_ROLES = frozenset({"admin", "super_admin", "manager"})
ORGANIZATION_SCOPED_STANDALONE_RESOURCE_KEYS = {
    "core": frozenset(
        {
            "departments",
            "clients",
            "currencies",
            "measurement-units",
            "client-categories",
            "poultry-types",
            "positions",
            "roles",
        }
    ),
}
WORKSPACE_RESOURCE_ALIASES = {
    "core": (
        {
            "source_module_key": "hr",
            "resource_keys": frozenset({"positions", "roles"}),
        },
    ),
}


class OrganizationService(BaseService):
    read_schema = OrganizationReadSchema

    def __init__(self, repository: OrganizationRepository) -> None:
        super().__init__(repository=repository)


class DepartmentModuleService(BaseService):
    read_schema = DepartmentModuleReadSchema

    def __init__(self, repository: DepartmentModuleRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _normalize_string_list(raw_value: Any) -> list[str]:
        if raw_value is None:
            return []
        if isinstance(raw_value, str):
            candidate = raw_value.strip()
            if not candidate:
                return []
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
        return normalized

    @staticmethod
    def _normalize_workspace_key(value: object | None) -> str:
        return str(value or "").strip().lower()

    @classmethod
    def _can_read_workspace_resource(
        cls,
        resource: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> bool:
        if actor is None:
            return True

        if WORKSPACE_RESOURCE_READ_PRIVILEGED_ROLES.intersection(actor.roles):
            return True

        permission_prefix = cls._normalize_workspace_key(resource.get("permission_prefix"))
        if not permission_prefix:
            return False

        read_permission = f"{permission_prefix}.read"
        return read_permission in actor.permissions or read_permission in actor.implicit_read_permissions

    @classmethod
    def _is_workspace_resource_organization_scoped(
        cls,
        module: dict[str, Any],
        resource: dict[str, Any],
    ) -> bool:
        if bool(module.get("is_department_assignable", True)):
            return True

        module_key = cls._normalize_workspace_key(module.get("key"))
        allowed_resource_keys = ORGANIZATION_SCOPED_STANDALONE_RESOURCE_KEYS.get(module_key)
        if allowed_resource_keys is None:
            return True

        return cls._normalize_workspace_key(resource.get("key")) in allowed_resource_keys

    @classmethod
    def _get_module_workspace_resources(
        cls,
        module: dict[str, Any],
        resources_by_module: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        module_key = cls._normalize_workspace_key(module.get("key"))
        combined_resources = [dict(resource) for resource in resources_by_module.get(module_key, [])]

        for alias in WORKSPACE_RESOURCE_ALIASES.get(module_key, ()):
            source_module_key = cls._normalize_workspace_key(alias.get("source_module_key"))
            allowed_resource_keys = {
                cls._normalize_workspace_key(resource_key)
                for resource_key in alias.get("resource_keys", ())
            }
            if not source_module_key or not allowed_resource_keys:
                continue

            for resource in resources_by_module.get(source_module_key, []):
                if cls._normalize_workspace_key(resource.get("key")) not in allowed_resource_keys:
                    continue

                aliased_resource = dict(resource)
                aliased_resource["api_module_key"] = (
                    cls._normalize_workspace_key(aliased_resource.get("api_module_key"))
                    or source_module_key
                )
                combined_resources.append(aliased_resource)

        deduplicated_resources: list[dict[str, Any]] = []
        seen_resource_keys: set[tuple[str, str]] = set()
        for resource in combined_resources:
            resource_identity = (
                cls._normalize_workspace_key(resource.get("key")),
                cls._normalize_workspace_key(resource.get("api_module_key")),
            )
            if resource_identity in seen_resource_keys:
                continue
            seen_resource_keys.add(resource_identity)
            deduplicated_resources.append(resource)

        return deduplicated_resources

    def _prepare_create_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        for field_name in ("implicit_read_permissions", "analytics_read_permissions"):
            if field_name in next_payload:
                next_payload[field_name] = self._normalize_string_list(next_payload.get(field_name))
        return next_payload

    def _prepare_update_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        next_payload.pop(self.repository.id_column, None)
        next_payload.pop("id", None)
        return self._prepare_create_payload(next_payload, actor=actor)

    async def list_workspace_modules(
        self,
        *,
        actor: CurrentActor | None = None,
    ) -> Result[dict[str, Any]]:
        modules = await self.repository.list(
            filters={"is_active": True},
            order_by=("sort_order", "name", "key", "id"),
        )
        resource_repository = WorkspaceResourceRepository(self.repository.db)
        resources = await resource_repository.list(
            filters={"is_active": True},
            order_by=("module_key", "sort_order", "name", "key", "id"),
        )

        resources_by_module: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for resource in resources:
            module_key = str(resource.get("module_key") or "").strip().lower()
            if module_key:
                resources_by_module[module_key].append(resource)

        def normalize_resource_key(resource: dict[str, Any]) -> str:
            return self._normalize_workspace_key(resource.get("key"))

        def normalize_resource_api_module_key(resource: dict[str, Any]) -> str:
            return self._normalize_workspace_key(resource.get("api_module_key"))

        def get_resource_sort_order(resource: dict[str, Any]) -> int:
            value = resource.get("sort_order")
            if isinstance(value, int):
                return value
            if isinstance(value, str):
                try:
                    return int(value.strip())
                except Exception:
                    return 100
            return 100

        items = [
            WorkspaceModuleMetaSchema.model_validate(
                {
                    **module,
                    "label": module.get("name"),
                    "resources": [
                        {
                            **resource,
                            "label": resource.get("name"),
                        }
                        for resource in sorted(
                            self._get_module_workspace_resources(module, resources_by_module),
                            key=lambda resource: (
                                get_resource_sort_order(resource),
                                str(resource.get("name") or ""),
                                normalize_resource_key(resource),
                                str(resource.get("id") or ""),
                            ),
                        )
                        if self._is_workspace_resource_organization_scoped(module, resource)
                        and self._can_read_workspace_resource(resource, actor=actor)
                    ],
                }
            )
            for module in modules
            if str(module.get("key") or "").strip().lower() not in HIDDEN_WORKSPACE_MODULE_KEYS
        ]
        return Result.ok_result(
            {
                "items": items,
                "total": len(items),
                "limit": len(items),
                "offset": 0,
                "has_more": False,
            }
        )


class DepartmentService(BaseService):
    read_schema = DepartmentReadSchema
    privileged_roles = frozenset({"admin", "super_admin", "manager"})
    department_management_permissions = frozenset(
        {
            "department.read",
            "department.create",
            "department.write",
            "department.delete",
        }
    )

    def __init__(self, repository: DepartmentRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _normalize_warehouse_code_seed(raw_value: object | None) -> str:
        candidate = str(raw_value or "").strip().upper()
        normalized = WAREHOUSE_CODE_SANITIZER_RE.sub("-", candidate).strip("-")
        return normalized or "WH"

    async def _build_default_warehouse_payload(
        self,
        department: dict[str, Any],
    ) -> dict[str, Any]:
        organization_id = str(department["organization_id"])
        department_id = str(department["id"])
        code_seed = self._normalize_warehouse_code_seed(department.get("code") or department.get("name"))
        base_code = f"{code_seed}-WH"[:80].rstrip("-") or "WH"
        candidate_code = base_code
        suffix = 2
        warehouse_repository = WarehouseRepository(self.repository.db)

        while await warehouse_repository.get_optional_by(
            filters={
                "organization_id": organization_id,
                "code": candidate_code,
            }
        ):
            suffix_value = f"-{suffix}"
            allowed_base_length = max(1, 80 - len(suffix_value))
            candidate_code = f"{base_code[:allowed_base_length].rstrip('-')}{suffix_value}"
            suffix += 1

        return {
            "organization_id": organization_id,
            "department_id": department_id,
            "name": "Asosiy ombor",
            "code": candidate_code,
            "description": f"Default warehouse for {department.get('name') or 'department'}",
            "is_default": True,
            "is_active": bool(department.get("is_active", True)),
        }

    async def _ensure_default_warehouse_for_department(
        self,
        department: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> None:
        warehouse_repository = WarehouseRepository(self.repository.db)
        existing = await warehouse_repository.get_optional_by(
            filters={
                "organization_id": str(department.get("organization_id") or ""),
                "department_id": str(department.get("id") or ""),
                "is_default": True,
            },
            order_by=("is_active DESC", "created_at", "id"),
        )
        if existing is not None:
            return

        warehouse_service = WarehouseService(warehouse_repository)
        await warehouse_service.create(
            await self._build_default_warehouse_payload(department),
            actor=None,
        )

    def _actor_has_department_access(
        self,
        actor: CurrentActor | None,
        action: str,
    ) -> bool:
        if actor is None:
            return True

        if self.privileged_roles.intersection(actor.roles):
            return True

        return f"department.{action}".lower() in actor.permissions

    async def _get_managed_department_scope(
        self,
        actor: CurrentActor,
    ) -> tuple[set[str], set[str]]:
        rows = await self.repository.db.fetch(
            """
            WITH RECURSIVE managed_departments AS (
                SELECT id, head_id
                FROM departments
                WHERE head_id = $1

                UNION

                SELECT d.id, d.head_id
                FROM departments AS d
                INNER JOIN managed_departments AS md
                  ON d.parent_department_id = md.id
            )
            SELECT id, head_id
            FROM managed_departments
            """,
            actor.employee_id,
        )

        managed_ids = {str(row["id"]) for row in rows}
        headed_ids = {
            str(row["id"])
            for row in rows
            if row.get("head_id") is not None and str(row["head_id"]) == str(actor.employee_id)
        }
        return managed_ids, headed_ids

    def _actor_has_global_department_visibility(
        self,
        actor: CurrentActor | None,
    ) -> bool:
        if actor is None:
            return True

        if self.privileged_roles.intersection(actor.roles):
            return True

        return bool(self.department_management_permissions.intersection(actor.permissions))

    @staticmethod
    def _collect_department_hierarchy_scope(
        departments: list[dict[str, Any]],
        seed_ids: set[str],
    ) -> set[str]:
        department_map = {
            str(department["id"]): department
            for department in departments
            if department.get("id") is not None
        }
        children_map: dict[str, list[str]] = defaultdict(list)

        for department in departments:
            department_id = str(department["id"]) if department.get("id") is not None else ""
            parent_department_id = (
                str(department["parent_department_id"])
                if department.get("parent_department_id") is not None
                else ""
            )
            if department_id and parent_department_id:
                children_map[parent_department_id].append(department_id)

        visible_ids: set[str] = set()

        for seed_id in seed_ids:
            if seed_id not in department_map:
                continue

            ancestor_id = seed_id
            while ancestor_id:
                if ancestor_id in visible_ids:
                    next_parent = department_map.get(ancestor_id, {}).get("parent_department_id")
                    ancestor_id = str(next_parent) if next_parent is not None else ""
                    continue

                visible_ids.add(ancestor_id)
                next_parent = department_map.get(ancestor_id, {}).get("parent_department_id")
                ancestor_id = str(next_parent) if next_parent is not None else ""

            queue = [seed_id]
            while queue:
                current_id = queue.pop()
                if current_id not in department_map:
                    continue
                if current_id in visible_ids:
                    queue.extend(
                        child_id
                        for child_id in children_map.get(current_id, [])
                        if child_id not in visible_ids
                    )
                    continue

                visible_ids.add(current_id)
                queue.extend(children_map.get(current_id, []))

        return visible_ids

    async def list_visible_to_actor(
        self,
        *,
        actor: CurrentActor | None = None,
    ) -> Result[dict[str, Any]]:
        filters = {"is_active": True}
        if actor is not None:
            filters["organization_id"] = actor.organization_id

        departments = await self.repository.list(
            filters=filters,
            order_by=("module_key", "name", "code", "id"),
        )

        if self._actor_has_global_department_visibility(actor):
            return Result.ok_result(
                {
                    "items": [self._map_read(item) for item in departments],
                    "total": len(departments),
                    "limit": len(departments),
                    "offset": 0,
                    "has_more": False,
                }
            )

        visible_departments = [
            department
            for department in departments
            if actor is not None
            and actor.department_id is not None
            and department.get("id") is not None
            and str(department["id"]) == str(actor.department_id)
        ]

        return Result.ok_result(
            {
                "items": [self._map_read(item) for item in visible_departments],
                "total": len(visible_departments),
                "limit": len(visible_departments),
                "offset": 0,
                "has_more": False,
            }
        )

    @staticmethod
    def _merge_scope_filters(
        filters: dict[str, Any] | None,
        managed_ids: set[str],
    ) -> dict[str, Any]:
        scoped_filters = dict(filters or {})
        existing_filter = scoped_filters.get("id")

        if existing_filter is None:
            scoped_filters["id"] = list(managed_ids)
            return scoped_filters

        if isinstance(existing_filter, (list, tuple, set)):
            scoped_filters["id"] = [value for value in existing_filter if str(value) in managed_ids]
            return scoped_filters

        scoped_filters["id"] = [existing_filter] if str(existing_filter) in managed_ids else []
        return scoped_filters

    async def _ensure_manageable_department(
        self,
        actor: CurrentActor,
        entity_id: Any,
    ) -> tuple[set[str], set[str]]:
        managed_ids, headed_ids = await self._get_managed_department_scope(actor)

        if str(entity_id) not in managed_ids:
            raise AccessDeniedError("You can only manage departments inside your scope")

        return managed_ids, headed_ids

    async def _enforce_scoped_department_create(
        self,
        actor: CurrentActor,
        payload: dict[str, Any],
    ) -> None:
        managed_ids, _ = await self._get_managed_department_scope(actor)
        parent_department_id = payload.get("parent_department_id")

        if parent_department_id is None:
            raise AccessDeniedError("Department heads can create only child departments inside their scope")

        if str(parent_department_id) not in managed_ids:
            raise AccessDeniedError("Parent department must belong to your management scope")

    async def _enforce_scoped_department_update(
        self,
        actor: CurrentActor,
        entity_id: Any,
        payload: dict[str, Any],
    ) -> None:
        managed_ids, headed_ids = await self._ensure_manageable_department(actor, entity_id)

        if "parent_department_id" not in payload:
            return

        next_parent_department_id = payload.get("parent_department_id")

        if next_parent_department_id is None:
            if str(entity_id) not in headed_ids:
                raise AccessDeniedError("Only the headed department itself can remain without a parent")
            return

        if str(next_parent_department_id) not in managed_ids:
            raise AccessDeniedError("Parent department must stay inside your management scope")

    async def list_with_pagination(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        actor: CurrentActor | None = None,
    ):
        if self._actor_has_department_access(actor, "read"):
            return await super().list_with_pagination(
                filters=filters,
                search=search,
                limit=limit,
                offset=offset,
                order_by=order_by,
                actor=actor,
            )

        managed_ids, _ = await self._get_managed_department_scope(actor)
        scoped_filters = self._merge_scope_filters(filters, managed_ids)
        return await super().list_with_pagination(
            filters=scoped_filters,
            search=search,
            limit=limit,
            offset=offset,
            order_by=order_by,
            actor=actor,
        )

    async def get_by_id(self, entity_id: Any, *, actor: CurrentActor | None = None):
        if not self._actor_has_department_access(actor, "read"):
            await self._ensure_manageable_department(actor, entity_id)
        return await super().get_by_id(entity_id, actor=actor)

    async def _validate_department_payload(
        self,
        payload: dict[str, Any],
        *,
        current_department_id: str | None = None,
    ) -> None:
        existing: dict[str, Any] | None = None
        if current_department_id is not None:
            existing = await self.repository.get_by_id(current_department_id)

        organization_id = payload.get("organization_id") or (existing or {}).get("organization_id")
        module_key = payload.get("module_key") or (existing or {}).get("module_key")
        parent_department_id = payload.get("parent_department_id", (existing or {}).get("parent_department_id"))
        head_id = payload.get("head_id", (existing or {}).get("head_id"))

        if organization_id is None:
            raise ValidationError("organization_id is required")

        if not module_key:
            raise ValidationError("module_key is required")

        department_module_repository = DepartmentModuleRepository(self.repository.db)
        department_module = await department_module_repository.get_optional_by(
            filters={"key": str(module_key)},
        )

        if department_module is None:
            raise ValidationError("module_key is invalid")
        if current_department_id is None or "module_key" in payload:
            if not bool(department_module.get("is_active", True)):
                raise ValidationError("module_key is inactive")
            if not bool(department_module.get("is_department_assignable", True)):
                raise ValidationError("module_key cannot be assigned to departments")

        if parent_department_id is not None:
            if current_department_id is not None and str(parent_department_id) == str(current_department_id):
                raise ValidationError("Department cannot be a parent of itself")

            parent_department = await self.repository.get_by_id(parent_department_id)

            if str(parent_department["organization_id"]) != str(organization_id):
                raise ValidationError("Parent department must belong to the same organization")

            if str(parent_department["module_key"]) != str(module_key):
                raise ValidationError("Parent department must belong to the same module")

            ancestor_id = parent_department.get("parent_department_id")
            visited_ids: set[str] = {str(parent_department_id)}

            while ancestor_id is not None:
                ancestor_key = str(ancestor_id)

                if current_department_id is not None and ancestor_key == str(current_department_id):
                    raise ValidationError("Department hierarchy cannot contain cycles")

                if ancestor_key in visited_ids:
                    raise ValidationError("Department hierarchy is invalid")

                visited_ids.add(ancestor_key)
                ancestor = await self.repository.get_by_id_optional(ancestor_id)
                if ancestor is None:
                    break
                ancestor_id = ancestor.get("parent_department_id")
        else:
            if current_department_id is None:
                existing_root = await self.repository.db.fetchrow(
                    """
                    SELECT id
                    FROM departments
                    WHERE organization_id = $1
                      AND module_key = $2
                      AND parent_department_id IS NULL
                    LIMIT 1
                    """,
                    organization_id,
                    str(module_key),
                )
            else:
                existing_root = await self.repository.db.fetchrow(
                    """
                    SELECT id
                    FROM departments
                    WHERE organization_id = $1
                      AND module_key = $2
                      AND parent_department_id IS NULL
                      AND id != $3
                    LIMIT 1
                    """,
                    organization_id,
                    str(module_key),
                    current_department_id,
                )
            if existing_root is not None:
                raise ValidationError("Only one root department is allowed for each module")

        if (
            current_department_id is not None
            and existing is not None
            and "module_key" in payload
            and str(existing.get("module_key") or "") != str(module_key)
        ):
            existing_child = await self.repository.db.fetchrow(
                """
                SELECT id
                FROM departments
                WHERE parent_department_id = $1
                LIMIT 1
                """,
                current_department_id,
            )
            if existing_child is not None:
                raise ValidationError("Department module cannot be changed while it has child departments")

        if head_id is not None:
            employee = await self.repository.db.fetchrow(
                """
                SELECT id, organization_id
                FROM employees
                WHERE id = $1
                LIMIT 1
                """,
                head_id,
            )
            if employee is None:
                raise ValidationError("Department head was not found")
            if str(employee["organization_id"]) != str(organization_id):
                raise ValidationError("Department head must belong to the same organization")

    async def create(self, payload: Any, *, actor: CurrentActor | None = None):
        data = self._payload_to_dict(payload)
        if not self._actor_has_department_access(actor, "create"):
            await self._enforce_scoped_department_create(actor, data)
        await self._validate_department_payload(data)
        async with self.repository.db.transaction():
            result = await super().create(data, actor=actor)
            created_department = dict(result.data.model_dump()) if result.ok and hasattr(result.data, "model_dump") else None
            if result.ok and created_department is not None:
                await self._ensure_default_warehouse_for_department(created_department, actor=actor)
            organization_id = (
                str(getattr(result.data, "organization_id", "") or "")
                if result.ok
                else ""
            ).strip()
            if not organization_id:
                organization_id = str(data.get("organization_id") or "").strip()
            if not organization_id and actor is not None:
                organization_id = str(actor.organization_id or "").strip()

            if result.ok and organization_id:
                await sync_permissions_for_organizations(
                    self.repository.db,
                    organization_ids=[organization_id],
                    sync_privileged_roles=False,
                    dry_run=False,
                )
            return result

    async def update(self, entity_id: Any, payload: Any, *, actor: CurrentActor | None = None):
        data = self._payload_to_dict(payload)
        if not self._actor_has_department_access(actor, "write"):
            await self._enforce_scoped_department_update(actor, entity_id, data)
        await self._validate_department_payload(data, current_department_id=str(entity_id))
        return await super().update(entity_id, data, actor=actor)

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None):
        if not self._actor_has_department_access(actor, "delete"):
            _, headed_ids = await self._ensure_manageable_department(actor, entity_id)
            if str(entity_id) in headed_ids:
                raise AccessDeniedError("Department head cannot delete their own department")
        async with self.repository.db.transaction():
            await self.repository.db.execute(
                """
                DELETE FROM warehouses
                WHERE department_id = $1
                """,
                entity_id,
            )
            return await super().delete(entity_id, actor=actor)


class ClientService(BaseService):
    read_schema = ClientReadSchema

    def __init__(self, repository: ClientRepository) -> None:
        super().__init__(repository=repository)


class ClientDebtService(BaseService):
    read_schema = ClientDebtReadSchema

    def __init__(self, repository: ClientDebtRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _normalize_decimal(raw_value: object | None, *, field_name: str) -> Decimal:
        try:
            return Decimal(str(raw_value))
        except Exception as exc:
            raise ValidationError(f"{field_name} has an invalid value") from exc

    @staticmethod
    def _normalize_debt_date(raw_value: object | None, *, field_name: str) -> date | None:
        if raw_value is None:
            return None
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if isinstance(raw_value, date):
            return raw_value
        if not isinstance(raw_value, str):
            raise ValidationError(f"{field_name} has an invalid value")

        value_text = raw_value.strip()
        if not value_text:
            return None
        try:
            return date.fromisoformat(value_text)
        except ValueError:
            normalized = value_text.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized).date()
            except ValueError as exc:
                raise ValidationError(f"{field_name} has an invalid value") from exc

    @staticmethod
    def _resolve_debt_status(
        amount_total: Decimal,
        amount_paid: Decimal,
        requested_status: str | None,
    ) -> str:
        normalized_requested = str(requested_status or "").strip().lower()
        if normalized_requested == "cancelled":
            return "cancelled"
        if amount_paid <= Decimal("0"):
            return "open"
        if amount_paid >= amount_total:
            return "closed"
        return "partially_paid"

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                {
                    "name": "item_type",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(sorted(ITEM_TYPES)),
                    },
                },
                {
                    "name": "status",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(list(CLIENT_DEBT_STATUSES)),
                    },
                },
                {
                    "name": "item_key",
                    "reference": {
                        "table": ITEM_KEY_REFERENCE_TABLE,
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": [],
                    },
                },
            ]
        )
        return fields

    async def get_reference_options(
        self,
        field_name: str,
        *,
        db,
        actor=None,
        search: str | None = None,
        values=None,
        limit: int = 25,
        extra_params=None,
    ) -> list[dict[str, str]] | None:
        if field_name != "item_key":
            return None

        normalized_item_type = str((extra_params or {}).get("item_type") or "").strip().lower()
        if normalized_item_type not in ITEM_TYPES:
            return []

        normalized_department_id = str((extra_params or {}).get("department_id") or "").strip() or None
        organization_id = str(
            (actor.organization_id if actor is not None else None)
            or (extra_params or {}).get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            return []

        normalized_values = [str(value).strip() for value in (values or []) if str(value).strip()]
        return await _fetch_inventory_item_key_options(
            db=db,
            organization_id=organization_id,
            item_type=normalized_item_type,
            department_id=normalized_department_id,
            search=search,
            values=normalized_values,
            limit=limit,
        )

    async def _prepare_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        existing_item_type = existing.get("item_type") if existing is not None else None
        existing_item_key = existing.get("item_key") if existing is not None else None
        existing_unit = existing.get("unit") if existing is not None else None
        item_type = str(next_payload.get("item_type") or existing_item_type or "").strip().lower()
        item_key = str(next_payload.get("item_key") or existing_item_key or "").strip()
        unit = normalize_stock_movement_unit(next_payload.get("unit") or existing_unit)
        department_id = str(
            next_payload.get("department_id")
            or (existing.get("department_id") if existing else None)
            or ""
        ).strip()
        organization_id = str(
            next_payload.get("organization_id")
            or (existing.get("organization_id") if existing else None)
            or (actor.organization_id if actor is not None else "")
            or ""
        ).strip()
        amount_total = self._normalize_decimal(
            next_payload.get("amount_total") if "amount_total" in next_payload else existing.get("amount_total") if existing else None,
            field_name="amount_total",
        )
        amount_paid = self._normalize_decimal(
            next_payload.get("amount_paid") if "amount_paid" in next_payload else existing.get("amount_paid") if existing else Decimal("0"),
            field_name="amount_paid",
        )
        quantity = self._normalize_decimal(
            next_payload.get("quantity") if "quantity" in next_payload else existing.get("quantity") if existing else None,
            field_name="quantity",
        )

        if item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        if not item_key:
            raise ValidationError("item_key is required")
        if not department_id:
            raise ValidationError("department_id is required")
        if not organization_id:
            raise ValidationError("organization_id is required")
        if amount_total < Decimal("0"):
            raise ValidationError("amount_total must be non-negative")
        if amount_paid < Decimal("0"):
            raise ValidationError("amount_paid must be non-negative")
        if amount_paid > amount_total:
            raise ValidationError("amount_paid cannot exceed amount_total")
        if quantity <= Decimal("0"):
            raise ValidationError("quantity must be positive")
        issued_on = self._normalize_debt_date(
            next_payload.get("issued_on")
            if "issued_on" in next_payload
            else existing.get("issued_on")
            if existing
            else None,
            field_name="issued_on",
        )
        due_on = self._normalize_debt_date(
            next_payload.get("due_on")
            if "due_on" in next_payload
            else existing.get("due_on")
            if existing
            else None,
            field_name="due_on",
        )
        if issued_on is not None and due_on is not None and due_on < issued_on:
            raise ValidationError("due_on cannot be before issued_on")

        if not await _inventory_item_key_exists(
            db=self.repository.db,
            organization_id=organization_id,
            item_type=item_type,
            item_key=item_key,
            department_id=department_id,
        ):
            raise ValidationError("item_key is invalid for selected item_type")

        next_payload["item_type"] = item_type
        next_payload["item_key"] = item_key
        next_payload["unit"] = unit
        next_payload["department_id"] = department_id
        next_payload["organization_id"] = organization_id
        next_payload["amount_total"] = str(amount_total)
        next_payload["amount_paid"] = str(amount_paid)
        next_payload["quantity"] = str(quantity)
        next_payload["status"] = self._resolve_debt_status(
            amount_total=amount_total,
            amount_paid=amount_paid,
            requested_status=next_payload.get("status") if "status" in next_payload else existing.get("status") if existing else None,
        )
        return next_payload

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return await self._prepare_payload(data, actor=actor, existing=None)

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(data)
        if "organization_id" in next_payload and str(next_payload["organization_id"]) != str(existing["organization_id"]):
            raise ValidationError("organization_id is immutable")
        if "department_id" in next_payload and str(next_payload["department_id"]) != str(existing["department_id"]):
            raise ValidationError("department_id is immutable")
        if "client_id" in next_payload and str(next_payload["client_id"]) != str(existing["client_id"]):
            raise ValidationError("client_id is immutable")
        return await self._prepare_payload(next_payload, actor=actor, existing=existing)


class CurrencyService(BaseService):
    read_schema = CurrencyReadSchema

    def __init__(self, repository: CurrencyRepository) -> None:
        super().__init__(repository=repository)

    def _normalize_currency_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        next_payload = dict(payload)

        if "code" in next_payload and next_payload["code"] is not None:
            normalized_code = str(next_payload["code"]).strip().upper()
            if not normalized_code:
                raise ValidationError("code is required")
            next_payload["code"] = normalized_code

        if "name" in next_payload and next_payload["name"] is not None:
            normalized_name = str(next_payload["name"]).strip()
            if not normalized_name:
                raise ValidationError("name is required")
            next_payload["name"] = normalized_name

        if "symbol" in next_payload:
            normalized_symbol = str(next_payload["symbol"] or "").strip()
            next_payload["symbol"] = normalized_symbol or None

        if "description" in next_payload:
            normalized_description = str(next_payload["description"] or "").strip()
            next_payload["description"] = normalized_description or None

        return next_payload

    async def _has_active_default_currency(
        self,
        organization_id: str,
        *,
        exclude_id: str | None = None,
    ) -> bool:
        if exclude_id is None:
            rows = await self.repository.db.fetch(
                """
                SELECT id
                FROM currencies
                WHERE organization_id = $1
                  AND is_active = true
                  AND is_default = true
                LIMIT 1
                """,
                organization_id,
            )
        else:
            rows = await self.repository.db.fetch(
                """
                SELECT id
                FROM currencies
                WHERE organization_id = $1
                  AND is_active = true
                  AND is_default = true
                  AND id != $2
                LIMIT 1
                """,
                organization_id,
                exclude_id,
            )
        return bool(rows)

    async def _find_fallback_currency_id(
        self,
        organization_id: str,
        *,
        exclude_id: str | None = None,
    ) -> str | None:
        if exclude_id is None:
            row = await self.repository.db.fetchrow(
                """
                SELECT id
                FROM currencies
                WHERE organization_id = $1
                  AND is_active = true
                ORDER BY is_default DESC, sort_order ASC, name ASC, code ASC, id ASC
                LIMIT 1
                """,
                organization_id,
            )
        else:
            row = await self.repository.db.fetchrow(
                """
                SELECT id
                FROM currencies
                WHERE organization_id = $1
                  AND is_active = true
                  AND id != $2
                ORDER BY is_default DESC, sort_order ASC, name ASC, code ASC, id ASC
                LIMIT 1
                """,
                organization_id,
                exclude_id,
            )
        if row is None:
            return None
        return str(row["id"])

    async def _clear_default_currency(
        self,
        organization_id: str,
        *,
        exclude_id: str | None = None,
    ) -> None:
        if exclude_id is None:
            await self.repository.db.execute(
                """
                UPDATE currencies
                SET is_default = false
                WHERE organization_id = $1
                  AND is_default = true
                """,
                organization_id,
            )
            return

        await self.repository.db.execute(
            """
            UPDATE currencies
            SET is_default = false
            WHERE organization_id = $1
              AND is_default = true
              AND id != $2
            """,
            organization_id,
            exclude_id,
        )

    async def _ensure_default_currency_state(
        self,
        organization_id: str,
        *,
        entity_id: str | None = None,
        is_default: bool,
        is_active: bool,
    ) -> None:
        if is_default and is_active:
            await self._clear_default_currency(organization_id, exclude_id=entity_id)
            return

        has_other_active_default = await self._has_active_default_currency(
            organization_id,
            exclude_id=entity_id,
        )
        if has_other_active_default:
            return

        fallback_id = await self._find_fallback_currency_id(organization_id, exclude_id=entity_id)
        if fallback_id is not None:
            await self.repository.db.execute(
                """
                UPDATE currencies
                SET is_default = true
                WHERE id = $1
                """,
                fallback_id,
            )
            return

        if entity_id is not None and not is_active:
            raise ValidationError("organization must have at least one active currency")

    async def create(self, payload: Any, *, actor: CurrentActor | None = None):
        data = self._normalize_currency_payload(self._payload_to_dict(payload))
        organization_id = (
            str(data["organization_id"])
            if data.get("organization_id") is not None
            else actor.organization_id
            if actor is not None
            else ""
        ).strip()
        if organization_id and "is_default" not in data and not await self._has_active_default_currency(organization_id):
            data["is_default"] = True

        async with self.repository.db.transaction():
            result = await super().create(data, actor=actor)
            if not result.ok:
                return result

            created = dict(result.data)
            await self._ensure_default_currency_state(
                str(created["organization_id"]),
                entity_id=str(created["id"]),
                is_default=bool(created.get("is_default")),
                is_active=bool(created.get("is_active", True)),
            )
            refreshed = await self.repository.get_by_id(str(created["id"]))
        return Result.ok_result(self._map_read(refreshed))

    async def update(self, entity_id: Any, payload: Any, *, actor: CurrentActor | None = None):
        data = self._normalize_currency_payload(self._payload_to_dict(payload))
        existing = await self.repository.get_by_id(entity_id)
        organization_id = str(existing["organization_id"])
        next_is_active = bool(data.get("is_active", existing.get("is_active", True)))
        next_is_default = bool(data.get("is_default", existing.get("is_default", False)))

        async with self.repository.db.transaction():
            result = await super().update(entity_id, data, actor=actor)
            if not result.ok:
                return result

            await self._ensure_default_currency_state(
                organization_id,
                entity_id=str(entity_id),
                is_default=next_is_default,
                is_active=next_is_active,
            )
            refreshed = await self.repository.get_by_id(entity_id)
        return Result.ok_result(self._map_read(refreshed))

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None):
        existing = await self.repository.get_by_id(entity_id)
        organization_id = str(existing["organization_id"])
        is_default = bool(existing.get("is_default", False))

        if is_default and await self._find_fallback_currency_id(organization_id, exclude_id=str(entity_id)) is None:
            raise ValidationError("organization must have at least one active currency")

        async with self.repository.db.transaction():
            result = await super().delete(entity_id, actor=actor)
            if not result.ok or not is_default:
                return result

            fallback_id = await self._find_fallback_currency_id(organization_id)
            if fallback_id is not None:
                await self.repository.db.execute(
                    """
                    UPDATE currencies
                    SET is_default = true
                    WHERE id = $1
                    """,
                    fallback_id,
                )
        return result


class PoultryTypeService(BaseService):
    read_schema = PoultryTypeReadSchema

    def __init__(self, repository: PoultryTypeRepository) -> None:
        super().__init__(repository=repository)


class MeasurementUnitService(BaseService):
    read_schema = MeasurementUnitReadSchema

    def __init__(self, repository: MeasurementUnitRepository) -> None:
        super().__init__(repository=repository)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        next_payload = dict(payload)

        if "code" in next_payload and next_payload["code"] is not None:
            normalized_code = str(next_payload["code"]).strip().lower()
            if not normalized_code:
                raise ValidationError("code is required")
            next_payload["code"] = normalized_code

        if "name" in next_payload and next_payload["name"] is not None:
            normalized_name = str(next_payload["name"]).strip()
            if not normalized_name:
                raise ValidationError("name is required")
            next_payload["name"] = normalized_name

        if "description" in next_payload:
            normalized_description = str(next_payload["description"] or "").strip()
            next_payload["description"] = normalized_description or None

        return next_payload

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return self._normalize_payload(data)

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any] | None = None,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return self._normalize_payload(data)


class ClientCategoryService(BaseService):
    read_schema = ClientCategoryReadSchema

    def __init__(self, repository: ClientCategoryRepository) -> None:
        super().__init__(repository=repository)

    def _normalize_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        next_payload = dict(payload)

        if "code" in next_payload and next_payload["code"] is not None:
            normalized_code = str(next_payload["code"]).strip().lower()
            if not normalized_code:
                raise ValidationError("code is required")
            next_payload["code"] = normalized_code

        if "name" in next_payload and next_payload["name"] is not None:
            normalized_name = str(next_payload["name"]).strip()
            if not normalized_name:
                raise ValidationError("name is required")
            next_payload["name"] = normalized_name

        if "description" in next_payload:
            normalized_description = str(next_payload["description"] or "").strip()
            next_payload["description"] = normalized_description or None

        return next_payload

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return self._normalize_payload(data)

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any] | None = None,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return self._normalize_payload(data)


class WarehouseService(BaseService):
    read_schema = WarehouseReadSchema

    def __init__(self, repository: WarehouseRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _normalize_code(raw_value: object | None) -> str:
        candidate = str(raw_value or "").strip().upper()
        normalized = WAREHOUSE_CODE_SANITIZER_RE.sub("-", candidate).strip("-")
        if not normalized:
            raise ValidationError("code is required")
        return normalized[:80]

    @staticmethod
    def _normalize_name(raw_value: object | None) -> str:
        normalized = str(raw_value or "").strip()
        if not normalized:
            raise ValidationError("name is required")
        return normalized[:160]

    async def _get_department_row(self, department_id: str) -> dict[str, Any]:
        row = await self.repository.db.fetchrow(
            """
            SELECT id, organization_id, is_active
            FROM departments
            WHERE id = $1
            LIMIT 1
            """,
            department_id,
        )
        if row is None:
            raise ValidationError("department_id is invalid")
        return dict(row)

    async def _clear_other_defaults(
        self,
        department_id: str,
        *,
        exclude_id: str | None = None,
    ) -> None:
        if exclude_id is None:
            await self.repository.db.execute(
                """
                UPDATE warehouses
                SET is_default = false
                WHERE department_id = $1
                  AND is_default = true
                """,
                department_id,
            )
            return

        await self.repository.db.execute(
            """
            UPDATE warehouses
            SET is_default = false
            WHERE department_id = $1
              AND is_default = true
              AND id != $2
            """,
            department_id,
            exclude_id,
        )

    async def _get_department_fallback_warehouse_id(
        self,
        department_id: str,
        *,
        exclude_id: str | None = None,
    ) -> str | None:
        if exclude_id is None:
            row = await self.repository.db.fetchrow(
                """
                SELECT id
                FROM warehouses
                WHERE department_id = $1
                ORDER BY is_active DESC, is_default DESC, created_at ASC, id ASC
                LIMIT 1
                """,
                department_id,
            )
        else:
            row = await self.repository.db.fetchrow(
                """
                SELECT id
                FROM warehouses
                WHERE department_id = $1
                  AND id != $2
                ORDER BY is_active DESC, is_default DESC, created_at ASC, id ASC
                LIMIT 1
                """,
                department_id,
                exclude_id,
            )
        return str(row["id"]) if row is not None else None

    async def _ensure_default_state(
        self,
        *,
        organization_id: str,
        department_id: str,
        entity_id: str | None,
        is_default: bool,
        is_active: bool,
    ) -> None:
        if is_default:
            await self._clear_other_defaults(department_id, exclude_id=entity_id)
            return

        existing_default = await self.repository.get_optional_by(
            filters={
                "department_id": department_id,
                "is_default": True,
            }
        )
        if existing_default is not None:
            return

        fallback_id = await self._get_department_fallback_warehouse_id(
            department_id,
            exclude_id=entity_id,
        )
        if fallback_id is None:
            if not is_active:
                raise ValidationError("department must keep at least one active warehouse")
            return

        await self.repository.db.execute(
            """
            UPDATE warehouses
            SET is_default = true
            WHERE id = $1
            """,
            fallback_id,
        )

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(data)
        organization_id = str(
            next_payload.get("organization_id")
            or (actor.organization_id if actor is not None else "")
        ).strip()
        department_id = str(next_payload.get("department_id") or "").strip()

        if not organization_id:
            raise ValidationError("organization_id is required")
        if not department_id:
            raise ValidationError("department_id is required")

        department_row = await self._get_department_row(department_id)
        if str(department_row["organization_id"]) != organization_id:
            raise ValidationError("department must belong to the same organization")

        next_payload["organization_id"] = organization_id
        next_payload["department_id"] = department_id
        next_payload["name"] = self._normalize_name(next_payload.get("name"))
        next_payload["code"] = self._normalize_code(next_payload.get("code"))
        next_payload["description"] = str(next_payload.get("description") or "").strip() or None

        existing_count = await self.repository.count(
            filters={
                "organization_id": organization_id,
                "department_id": department_id,
            }
        )
        is_default = True if existing_count == 0 else bool(next_payload.get("is_default", False))
        next_payload["is_default"] = is_default
        next_payload["is_active"] = bool(next_payload.get("is_active", True))
        await self._ensure_default_state(
            organization_id=organization_id,
            department_id=department_id,
            entity_id=None,
            is_default=is_default,
            is_active=bool(next_payload["is_active"]),
        )
        return next_payload

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(data)
        if "organization_id" in next_payload and str(next_payload["organization_id"]) != str(existing["organization_id"]):
            raise ValidationError("organization_id is immutable")
        if "department_id" in next_payload and str(next_payload["department_id"]) != str(existing["department_id"]):
            raise ValidationError("department_id is immutable")

        if "name" in next_payload:
            next_payload["name"] = self._normalize_name(next_payload.get("name"))
        if "code" in next_payload:
            next_payload["code"] = self._normalize_code(next_payload.get("code"))
        if "description" in next_payload:
            next_payload["description"] = str(next_payload.get("description") or "").strip() or None

        is_default = bool(next_payload.get("is_default", existing.get("is_default", False)))
        is_active = bool(next_payload.get("is_active", existing.get("is_active", True)))
        await self._ensure_default_state(
            organization_id=str(existing["organization_id"]),
            department_id=str(existing["department_id"]),
            entity_id=str(entity_id),
            is_default=is_default,
            is_active=is_active,
        )
        return next_payload

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None):
        warehouse = await self.repository.get_by_id(entity_id)
        department_id = str(warehouse["department_id"])
        warehouses_in_department = await self.repository.count(filters={"department_id": department_id})
        if warehouses_in_department <= 1:
            raise ValidationError("department must keep at least one warehouse")

        async with self.repository.db.transaction():
            result = await super().delete(entity_id, actor=actor)
            if bool(warehouse.get("is_default")):
                fallback_id = await self._get_department_fallback_warehouse_id(
                    department_id,
                    exclude_id=str(entity_id),
                )
                if fallback_id is not None:
                    await self.repository.db.execute(
                        """
                        UPDATE warehouses
                        SET is_default = true
                        WHERE id = $1
                        """,
                        fallback_id,
                    )
            return result


__all__ = [
    "OrganizationService",
    "DepartmentModuleService",
    "DepartmentService",
    "WarehouseService",
    "ClientService",
    "ClientDebtService",
    "CurrencyService",
    "PoultryTypeService",
]
