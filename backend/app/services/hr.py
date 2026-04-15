from __future__ import annotations

from typing import Any, Sequence
from uuid import UUID

from app.core.exceptions import AccessDeniedError, ValidationError
from app.repositories.hr import (
    EmployeeRepository,
    PermissionRepository,
    PositionRepository,
    RoleRepository,
)
from app.schemas.hr import (
    EmployeeReadSchema,
    PermissionReadSchema,
    PositionReadSchema,
    RoleReadSchema,
)
from app.services.base import BaseService
from app.utils.password import hash_password, is_hashed_password
from app.utils.result import Result


PRIVILEGED_HR_ROLE_EDITORS = frozenset({"admin", "super_admin"})
SENSITIVE_EMPLOYEE_FIELDS = frozenset({"password"})


def _normalize_relation_ids(value: Any, *, field_name: str) -> list[str]:
    if value is None or value == "":
        return []
    if not isinstance(value, (list, tuple, set)):
        raise ValidationError(f"{field_name} must be an array")

    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        text = str(item).strip()
        if not text:
            continue
        try:
            normalized_uuid = str(UUID(text))
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{field_name} contains an invalid UUID") from exc
        if normalized_uuid in seen:
            continue
        seen.add(normalized_uuid)
        normalized.append(normalized_uuid)
    return normalized


def _build_relation_meta_field(
    *,
    name: str,
    label: str,
    table: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "label": label,
        "type": "json",
        "database_type": "uuid[]",
        "nullable": True,
        "required": False,
        "readonly": False,
        "has_default": False,
        "is_primary_key": False,
        "is_foreign_key": False,
        "reference": {
            "table": table,
            "column": "id",
            "multiple": True,
        },
    }


class EmployeeService(BaseService):
    read_schema = EmployeeReadSchema

    def __init__(self, repository: EmployeeRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        return [
            *(await super().get_additional_meta_fields(db)),
            _build_relation_meta_field(name="role_ids", label="Roles", table="roles"),
        ]

    @staticmethod
    def _actor_can_manage_security_fields(actor) -> bool:
        if actor is None:
            return True
        actor_roles = {str(role).strip().lower() for role in getattr(actor, "roles", ())}
        return bool(actor_roles.intersection(PRIVILEGED_HR_ROLE_EDITORS))

    @classmethod
    def _assert_actor_can_manage_security_fields(cls, actor, *, field_name: str) -> None:
        if cls._actor_can_manage_security_fields(actor):
            return
        raise AccessDeniedError(f"Only admins can change {field_name}")

    @staticmethod
    def _sanitize_employee_row(row: dict[str, Any]) -> dict[str, Any]:
        sanitized = dict(row)
        for field_name in SENSITIVE_EMPLOYEE_FIELDS:
            sanitized.pop(field_name, None)
        return sanitized

    def _prepare_create_payload(
        self,
        payload: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        password = str(next_payload.get("password") or "").strip()
        if not password:
            raise ValidationError("password is required")
        next_payload["password"] = password if is_hashed_password(password) else hash_password(password)
        return next_payload

    def _prepare_update_payload(
        self,
        payload: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        next_payload.pop(self.repository.id_column, None)
        next_payload.pop("id", None)
        if "password" not in next_payload:
            return next_payload

        password_text = str(next_payload.get("password") or "").strip()
        if not password_text:
            next_payload.pop("password", None)
            return next_payload

        next_payload["password"] = (
            password_text if is_hashed_password(password_text) else hash_password(password_text)
        )
        return next_payload

    @staticmethod
    def _extract_role_ids(payload: dict[str, Any]) -> list[str] | None:
        if "role_ids" not in payload:
            return None
        raw_value = payload.pop("role_ids")
        return _normalize_relation_ids(raw_value, field_name="role_ids")

    async def _validate_role_ids(self, organization_id: str, role_ids: Sequence[str]) -> None:
        if not role_ids:
            return
        rows = await self.repository.get_role_rows(role_ids)
        if len(rows) != len(role_ids):
            raise ValidationError("Some roles do not exist")
        for row in rows:
            if str(row["organization_id"]) != str(organization_id):
                raise ValidationError("Assigned roles must belong to the same organization")
            if row.get("is_active") is False:
                raise ValidationError("Assigned roles must be active")

    async def _enrich_employee_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        role_map = await self.repository.get_role_ids_map(
            [row["id"] for row in rows if row.get("id") is not None]
        )
        enriched: list[dict[str, Any]] = []
        for row in rows:
            next_row = self._sanitize_employee_row(row)
            next_row["role_ids"] = role_map.get(str(row["id"]), [])
            enriched.append(next_row)
        return enriched

    async def _capture_audit_snapshot(
        self,
        entity_id: Any,
        *,
        entity: dict[str, Any] | None = None,
        actor=None,
    ) -> dict[str, Any] | None:
        source_entity = dict(entity) if entity is not None else await self.repository.get_by_id_optional(entity_id)
        if source_entity is None:
            return None

        if "role_ids" not in source_entity:
            role_map = await self.repository.get_role_ids_map([str(entity_id)])
            source_entity["role_ids"] = role_map.get(str(entity_id), [])

        # Keep password in audit snapshots so password-only updates are auditable.
        # Redaction is handled centrally by audit normalization utilities.
        if "password" not in source_entity:
            raw_entity = await self.repository.get_by_id_optional(entity_id)
            if raw_entity is not None and raw_entity.get("password") is not None:
                source_entity["password"] = raw_entity.get("password")

        return dict(source_entity)

    async def list_with_pagination(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        actor=None,
    ) -> Result[dict[str, Any]]:
        scoped_filters = self._scope_filters_to_actor(filters, actor=actor)
        rows = await self.repository.list(
            filters=scoped_filters,
            search=search,
            search_columns=self.get_searchable_columns(),
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        enriched_rows = await self._enrich_employee_rows([dict(row) for row in rows])
        total = await self.repository.count(
            filters=scoped_filters,
            search=search,
            search_columns=self.get_searchable_columns(),
        )
        return Result.ok_result(
            {
                "items": [self._map_read(row) for row in enriched_rows],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(enriched_rows)) < total,
            }
        )

    async def get_by_id(self, entity_id: Any, *, actor=None) -> Result[Any]:
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        enriched = (await self._enrich_employee_rows([entity]))[0]
        return Result.ok_result(self._map_read(enriched))

    async def create(self, payload: Any, *, actor=None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        role_ids = self._extract_role_ids(data)
        if role_ids is not None:
            self._assert_actor_can_manage_security_fields(actor, field_name="employee roles")
        prepared = self._prepare_create_payload(data, actor=actor)
        prepared = self._apply_actor_organization_on_create(prepared, actor=actor)
        organization_id = str(prepared.get("organization_id") or "")
        await self._validate_role_ids(organization_id, role_ids or [])
        async with self.repository.db.transaction():
            entity = await self.repository.create(prepared)
            await self.repository.replace_roles(entity["id"], role_ids or [])
            enriched = (await self._enrich_employee_rows([entity]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity["id"],
                entity=enriched,
                actor=actor,
            )
            await self._record_audit_event(
                action="create",
                entity_id=entity["id"],
                before_data=None,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched))

    async def update(self, entity_id: Any, payload: Any, *, actor=None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        role_ids = self._extract_role_ids(data)
        if role_ids is not None:
            self._assert_actor_can_manage_security_fields(actor, field_name="employee roles")
        prepared = self._prepare_update_payload(data, actor=actor)
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=existing,
                actor=actor,
            )
            prepared = self._apply_actor_organization_on_update(prepared, actor=actor)
            next_organization_id = str(prepared.get("organization_id") or existing.get("organization_id") or "")
            current_role_ids = (await self._enrich_employee_rows([existing]))[0].get("role_ids", [])
            effective_role_ids = current_role_ids if role_ids is None else role_ids
            await self._validate_role_ids(next_organization_id, effective_role_ids or [])
            entity = await self.repository.update_by_id(entity_id, prepared) if prepared else existing
            if role_ids is not None:
                await self.repository.replace_roles(entity_id, role_ids)
            enriched = (await self._enrich_employee_rows([dict(entity)]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=enriched,
                actor=actor,
            )
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched))


class PositionService(BaseService):
    read_schema = PositionReadSchema

    def __init__(self, repository: PositionRepository) -> None:
        super().__init__(repository=repository)

    def _uses_department_scope(self) -> bool:
        return False

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        next_data["department_id"] = None
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        next_data["department_id"] = None
        return next_data


class RoleService(BaseService):
    read_schema = RoleReadSchema

    def __init__(self, repository: RoleRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        return [
            *(await super().get_additional_meta_fields(db)),
            _build_relation_meta_field(name="permission_ids", label="Permissions", table="permissions"),
        ]

    @staticmethod
    def _extract_permission_ids(payload: dict[str, Any]) -> list[str] | None:
        if "permission_ids" not in payload:
            return None
        raw_value = payload.pop("permission_ids")
        return _normalize_relation_ids(raw_value, field_name="permission_ids")

    @staticmethod
    def _actor_can_manage_security_fields(actor) -> bool:
        if actor is None:
            return True
        actor_roles = {str(role).strip().lower() for role in getattr(actor, "roles", ())}
        return bool(actor_roles.intersection(PRIVILEGED_HR_ROLE_EDITORS))

    @classmethod
    def _assert_actor_can_manage_security_fields(cls, actor, *, field_name: str) -> None:
        if cls._actor_can_manage_security_fields(actor):
            return
        raise AccessDeniedError(f"Only admins can change {field_name}")

    async def _validate_permission_ids(self, organization_id: str, permission_ids: Sequence[str]) -> None:
        if not permission_ids:
            return
        rows = await self.repository.get_permission_rows(permission_ids)
        if len(rows) != len(permission_ids):
            raise ValidationError("Some permissions do not exist")
        for row in rows:
            if str(row["organization_id"]) != str(organization_id):
                raise ValidationError("Assigned permissions must belong to the same organization")
            if row.get("is_active") is False:
                raise ValidationError("Assigned permissions must be active")

    async def _enrich_role_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        permission_map = await self.repository.get_permission_ids_map(
            [row["id"] for row in rows if row.get("id") is not None]
        )
        enriched: list[dict[str, Any]] = []
        for row in rows:
            next_row = dict(row)
            next_row["permission_ids"] = permission_map.get(str(row["id"]), [])
            enriched.append(next_row)
        return enriched

    async def _capture_audit_snapshot(
        self,
        entity_id: Any,
        *,
        entity: dict[str, Any] | None = None,
        actor=None,
    ) -> dict[str, Any] | None:
        source_entity = dict(entity) if entity is not None else await self.repository.get_by_id_optional(entity_id)
        if source_entity is None:
            return None
        if "permission_ids" not in source_entity:
            source_entity = (await self._enrich_role_rows([source_entity]))[0]
        return dict(source_entity)

    async def list_with_pagination(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        actor=None,
    ) -> Result[dict[str, Any]]:
        scoped_filters = self._scope_filters_to_actor(filters, actor=actor)
        rows = await self.repository.list(
            filters=scoped_filters,
            search=search,
            search_columns=self.get_searchable_columns(),
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        enriched_rows = await self._enrich_role_rows([dict(row) for row in rows])
        total = await self.repository.count(
            filters=scoped_filters,
            search=search,
            search_columns=self.get_searchable_columns(),
        )
        return Result.ok_result(
            {
                "items": [self._map_read(row) for row in enriched_rows],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(enriched_rows)) < total,
            }
        )

    async def get_by_id(self, entity_id: Any, *, actor=None) -> Result[Any]:
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        enriched = (await self._enrich_role_rows([entity]))[0]
        return Result.ok_result(self._map_read(enriched))

    async def create(self, payload: Any, *, actor=None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        permission_ids = self._extract_permission_ids(data)
        if permission_ids is not None:
            self._assert_actor_can_manage_security_fields(actor, field_name="role permissions")
        prepared = self._apply_actor_organization_on_create(data, actor=actor)
        organization_id = str(prepared.get("organization_id") or "")
        await self._validate_permission_ids(organization_id, permission_ids or [])
        async with self.repository.db.transaction():
            entity = await self.repository.create(prepared)
            await self.repository.replace_permissions(entity["id"], permission_ids or [])
            enriched = (await self._enrich_role_rows([entity]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity["id"],
                entity=enriched,
                actor=actor,
            )
            await self._record_audit_event(
                action="create",
                entity_id=entity["id"],
                before_data=None,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched))

    async def update(self, entity_id: Any, payload: Any, *, actor=None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        permission_ids = self._extract_permission_ids(data)
        if permission_ids is not None:
            self._assert_actor_can_manage_security_fields(actor, field_name="role permissions")
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=existing,
                actor=actor,
            )
            prepared = self._apply_actor_organization_on_update(data, actor=actor)
            next_organization_id = str(prepared.get("organization_id") or existing.get("organization_id") or "")
            current_permission_ids = (await self._enrich_role_rows([existing]))[0].get("permission_ids", [])
            effective_permission_ids = current_permission_ids if permission_ids is None else permission_ids
            await self._validate_permission_ids(next_organization_id, effective_permission_ids or [])
            entity = await self.repository.update_by_id(entity_id, prepared) if prepared else existing
            if permission_ids is not None:
                await self.repository.replace_permissions(entity_id, permission_ids)
            enriched = (await self._enrich_role_rows([dict(entity)]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=enriched,
                actor=actor,
            )
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched))


class PermissionService(BaseService):
    read_schema = PermissionReadSchema

    def __init__(self, repository: PermissionRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "EmployeeService",
    "PositionService",
    "RoleService",
    "PermissionService",
]
