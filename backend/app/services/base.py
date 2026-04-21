from __future__ import annotations

from abc import ABC
from datetime import date, datetime, time, timezone
import json
from typing import TYPE_CHECKING, Any, Mapping, Sequence
from uuid import UUID, uuid4

from app.core.exceptions import AccessDeniedError, NotFoundError, ValidationError
from app.models import Base
from app.repositories.base import BaseRepository
from app.repositories.core import CurrencyRepository
from app.repositories.system import AuditLogRepository
from app.services.telegram_alerts import enqueue_operational_admin_alert
from app.utils.audit import build_changed_fields, normalize_audit_snapshot, normalize_audit_value
from app.utils.result import Result

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


class BaseService(ABC):
    """Base async CRUD service that wraps repository calls with result objects."""

    read_schema = None
    audit_enabled = True

    def __init__(self, repository: BaseRepository) -> None:
        self.repository = repository

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return data

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> None:
        return None

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor: CurrentActor | None = None,
    ) -> None:
        return None

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor: CurrentActor | None = None,
    ) -> None:
        return None

    @staticmethod
    def _build_static_reference_options(values: list[str]) -> list[dict[str, str]]:
        return [{"value": value, "label": value} for value in values]

    _UNIT_ALIASES = {
        "pcs": "dona",
        "bosh": "dona",
        "l": "litr",
        "kilogram": "kg",
        "kilogramm": "kg",
    }

    async def _auto_resolve_measurement_unit(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        """Resolve `unit` code → `measurement_unit_id` FK when a table carries both.

        Service-layer helper for tables migrated to FK-based units. Pass
        `unit="kg"` in the payload and this auto-sets `measurement_unit_id`.
        If the payload already has `measurement_unit_id`, leaves it alone.
        """
        if not self.repository.has_column("measurement_unit_id"):
            return data
        if data.get("measurement_unit_id"):
            return data

        unit_raw = data.get("unit")
        if unit_raw is None and existing is not None:
            unit_raw = existing.get("unit")
        if unit_raw is None:
            if existing is not None and existing.get("measurement_unit_id"):
                data["measurement_unit_id"] = existing["measurement_unit_id"]
                return data
            unit_raw = "kg"

        unit_code = str(unit_raw).strip().lower()
        unit_code = self._UNIT_ALIASES.get(unit_code, unit_code)

        organization_id = data.get("organization_id") or (
            existing.get("organization_id") if existing is not None else None
        )
        if organization_id is None and self.repository.table == "stock_take_lines":
            stock_take_id = data.get("stock_take_id") or (
                existing.get("stock_take_id") if existing is not None else None
            )
            if stock_take_id:
                parent = await self.repository.db.fetchrow(
                    "SELECT organization_id FROM stock_takes WHERE id = $1",
                    stock_take_id,
                )
                if parent is not None:
                    organization_id = parent["organization_id"]

        if organization_id is None:
            raise ValidationError("cannot resolve measurement unit without organization_id")

        row = await self.repository.db.fetchrow(
            "SELECT id FROM measurement_units WHERE organization_id = $1 AND code = $2 LIMIT 1",
            organization_id,
            unit_code,
        )
        if row is None:
            row = await self.repository.db.fetchrow(
                "SELECT id FROM measurement_units WHERE organization_id = $1 AND code = 'kg' LIMIT 1",
                organization_id,
            )
        if row is None:
            raise ValidationError(f"measurement_unit not found for code '{unit_code}'")

        data["measurement_unit_id"] = row["id"]
        return data

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields: list[dict[str, Any]] = []
        if self.repository.has_column("currency"):
            fields.append(
                {
                    "name": "currency",
                    "label": "Currency",
                    "type": "string",
                    "database_type": "character varying",
                    "nullable": False,
                    "required": True,
                    "readonly": False,
                    "has_default": True,
                    "is_primary_key": False,
                    "is_foreign_key": False,
                    "reference": {
                        "table": "currencies",
                        "column": "code",
                        "label_column": "name",
                        "multiple": False,
                    },
                }
            )
        if self.repository.has_column("unit"):
            fields.append(
                {
                    "name": "unit",
                    "reference": {
                        "table": "measurement_units",
                        "column": "code",
                        "label_column": "name",
                        "multiple": False,
                    },
                }
            )
        if self.repository.has_column("category"):
            fields.append(
                {
                    "name": "category",
                    "reference": {
                        "table": "client_categories",
                        "column": "code",
                        "label_column": "name",
                        "multiple": False,
                    },
                }
            )
        return fields

    async def get_reference_options(
        self,
        field_name: str,
        *,
        db,
        actor: CurrentActor | None = None,
        search: str | None = None,
        values: Sequence[str] | None = None,
        limit: int = 25,
        extra_params: Mapping[str, Any] | None = None,
    ) -> list[dict[str, str]] | None:
        return None

    def get_searchable_columns(self) -> tuple[str, ...]:
        return self.repository.get_searchable_columns()

    def _payload_to_dict(self, payload: Any) -> dict[str, Any]:
        if payload is None:
            return {}
        if hasattr(payload, "model_dump"):
            return payload.model_dump(exclude_unset=True)
        if hasattr(payload, "dict"):
            return payload.dict(exclude_unset=True)
        if isinstance(payload, dict):
            return payload
        return dict(payload)

    def _map_read(self, row: dict[str, Any]) -> Any:
        schema = self.read_schema
        if schema is None:
            return row
        if hasattr(schema, "model_validate"):
            return schema.model_validate(row)
        if hasattr(schema, "from_orm"):
            return schema.from_orm(row)
        if hasattr(schema, "parse_obj"):
            return schema.parse_obj(row)
        return row

    def _normalize_audit_snapshot(
        self,
        value: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        return normalize_audit_snapshot(value)

    async def _capture_audit_snapshot(
        self,
        entity_id: Any,
        *,
        entity: Mapping[str, Any] | None = None,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any] | None:
        source_entity = dict(entity) if entity is not None else await self.repository.get_by_id_optional(entity_id)
        if source_entity is None:
            return None
        return dict(source_entity)

    async def _record_audit_event(
        self,
        *,
        action: str,
        entity_id: Any,
        before_data: Mapping[str, Any] | None,
        after_data: Mapping[str, Any] | None,
        actor: CurrentActor | None = None,
        context_data: Mapping[str, Any] | None = None,
    ) -> None:
        if not self.audit_enabled:
            return

        normalized_before = self._normalize_audit_snapshot(before_data)
        normalized_after = self._normalize_audit_snapshot(after_data)
        comparison_before = normalize_audit_snapshot(before_data, redact_sensitive=False)
        comparison_after = normalize_audit_snapshot(after_data, redact_sensitive=False)

        if action == "update" and comparison_before == comparison_after:
            return

        organization_id = (
            (after_data or {}).get("organization_id")
            or (before_data or {}).get("organization_id")
            or (actor.organization_id if actor is not None else None)
        )
        payload = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "actor_id": actor.employee_id if actor is not None else None,
            "entity_table": self.repository.table,
            "entity_id": str(entity_id),
            "action": action,
            "actor_username": actor.username if actor is not None else None,
            "changed_at": datetime.now(timezone.utc),
            "actor_roles": (
                json.dumps(sorted(actor.roles))
                if actor is not None
                else None
            ),
            "changed_fields": json.dumps(
                build_changed_fields(before_data, after_data, redact_sensitive=False)
            ),
            "before_data": (
                json.dumps(normalized_before)
                if normalized_before is not None
                else None
            ),
            "after_data": (
                json.dumps(normalized_after)
                if normalized_after is not None
                else None
            ),
            "context_data": (
                json.dumps(normalize_audit_value(context_data))
                if context_data is not None
                else None
            ),
        }
        audit_repository = AuditLogRepository(self.repository.db)
        await audit_repository.create(payload)

    def _normalize_uuid_payload_fields(
        self,
        payload: dict[str, Any],
        *,
        is_create: bool,
    ) -> dict[str, Any]:
        table = Base.metadata.tables.get(self.repository.table)
        if table is None:
            return payload

        id_column = self.repository.id_column
        next_payload = dict(payload)

        for column in table.columns:
            python_type = getattr(column.type, "python_type", None)
            if python_type is not UUID:
                continue

            column_name = str(column.name)
            if column_name not in next_payload:
                if is_create and column_name == id_column:
                    next_payload[id_column] = str(uuid4())
                continue

            raw_value = next_payload[column_name]
            if isinstance(raw_value, (list, tuple, set)):
                values = [str(item).strip() for item in raw_value]
                values = [value for value in values if value]
                if not values:
                    raw_value = None
                elif len(values) == 1:
                    raw_value = values[0]
                else:
                    raise ValidationError(f'Field "{column_name}" has an invalid value.')

            if column_name == id_column and is_create:
                if raw_value is None:
                    next_payload[id_column] = str(uuid4())
                    continue

                if isinstance(raw_value, UUID):
                    continue

                if not isinstance(raw_value, str):
                    value_text = str(raw_value).strip()
                else:
                    value_text = raw_value.strip()

                normalized_value = value_text.lower()
                if not value_text or normalized_value in {"", "null", "none", "undefined"}:
                    next_payload[id_column] = str(uuid4())
                    continue

                try:
                    next_payload[id_column] = str(UUID(value_text))
                    continue
                except ValueError as exc:
                    raise ValidationError('Field "id" has an invalid value.') from exc

            if raw_value is None:
                if not column.nullable:
                    raise ValidationError(f'Field "{column_name}" is required.')
                continue

            if isinstance(raw_value, UUID):
                continue

            if not isinstance(raw_value, str):
                raise ValidationError(f'Field "{column_name}" has an invalid value.')

            value_text = raw_value.strip()
            if value_text == '':
                if column.nullable:
                    next_payload[column_name] = None
                    continue

                raise ValidationError(f'Field "{column_name}" is required.')

            try:
                next_payload[column_name] = str(UUID(value_text))
            except ValueError as exc:
                raise ValidationError(f'Field "{column_name}" has an invalid value.') from exc

        return next_payload

    def _normalize_temporal_payload_fields(
        self,
        payload: dict[str, Any],
        *,
        is_create: bool,
    ) -> dict[str, Any]:
        table = Base.metadata.tables.get(self.repository.table)
        if table is None:
            return payload

        next_payload = dict(payload)

        for column in table.columns:
            column_name = str(column.name)
            if column_name not in next_payload:
                continue

            try:
                python_type = getattr(column.type, "python_type", None)
            except (NotImplementedError, AttributeError):
                python_type = None

            if python_type not in {date, datetime, time}:
                continue

            raw_value = next_payload[column_name]
            if raw_value is None:
                if not column.nullable and self._is_required_column(column_name):
                    raise ValidationError(f'Field "{column_name}" is required.')
                continue

            if python_type is date:
                if isinstance(raw_value, datetime):
                    next_payload[column_name] = raw_value.date()
                    continue
                if isinstance(raw_value, date):
                    continue

                if not isinstance(raw_value, str):
                    raise ValidationError(f'Field "{column_name}" has an invalid value.')

                value_text = raw_value.strip()
                if value_text == "":
                    if column.nullable:
                        next_payload[column_name] = None
                        continue
                    raise ValidationError(f'Field "{column_name}" is required.')

                try:
                    next_payload[column_name] = date.fromisoformat(value_text)
                    continue
                except ValueError:
                    normalized = value_text.replace("Z", "+00:00")
                    try:
                        next_payload[column_name] = datetime.fromisoformat(normalized).date()
                        continue
                    except ValueError as exc:
                        raise ValidationError(f'Field "{column_name}" has an invalid value.') from exc

            if python_type is datetime:
                if isinstance(raw_value, datetime):
                    continue
                if isinstance(raw_value, date):
                    next_payload[column_name] = datetime.combine(raw_value, time.min)
                    continue

                if not isinstance(raw_value, str):
                    raise ValidationError(f'Field "{column_name}" has an invalid value.')

                value_text = raw_value.strip()
                if value_text == "":
                    if column.nullable:
                        next_payload[column_name] = None
                        continue
                    raise ValidationError(f'Field "{column_name}" is required.')

                normalized = value_text.replace("Z", "+00:00")
                try:
                    next_payload[column_name] = datetime.fromisoformat(normalized)
                    continue
                except ValueError:
                    try:
                        next_payload[column_name] = datetime.combine(
                            date.fromisoformat(value_text),
                            time.min,
                        )
                        continue
                    except ValueError as exc:
                        raise ValidationError(f'Field "{column_name}" has an invalid value.') from exc

            if python_type is time:
                if isinstance(raw_value, time):
                    continue
                if isinstance(raw_value, datetime):
                    next_payload[column_name] = raw_value.time().replace(tzinfo=None)
                    continue

                if not isinstance(raw_value, str):
                    raise ValidationError(f'Field "{column_name}" has an invalid value.')

                value_text = raw_value.strip()
                if value_text == "":
                    if column.nullable:
                        next_payload[column_name] = None
                        continue
                    raise ValidationError(f'Field "{column_name}" is required.')

                try:
                    next_payload[column_name] = time.fromisoformat(value_text)
                    continue
                except ValueError as exc:
                    raise ValidationError(f'Field "{column_name}" has an invalid value.') from exc

        return next_payload

    def _prepare_create_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = self._normalize_uuid_payload_fields(payload, is_create=True)

        if self.repository.has_column("is_active"):
            active_value = next_payload.get("is_active")
            if active_value is None:
                next_payload["is_active"] = True

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
        next_payload = self._normalize_uuid_payload_fields(next_payload, is_create=False)
        return next_payload

    async def _get_default_organization_currency_code(self, organization_id: str) -> str | None:
        currency_repository = CurrencyRepository(self.repository.db)
        row = await currency_repository.get_optional_by(
            filters={
                "organization_id": organization_id,
                "is_active": True,
            },
            order_by=("is_default desc", "sort_order", "name", "code", "id"),
        )
        if row is None:
            return None
        return str(row["code"]).strip().upper()

    async def _validate_catalog_fields(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
        existing: Mapping[str, Any] | None = None,
        is_create: bool,
    ) -> dict[str, Any]:
        if not self.repository.has_column("currency"):
            return payload

        organization_id = (
            str(payload["organization_id"])
            if payload.get("organization_id") is not None
            else str(existing["organization_id"])
            if existing is not None and existing.get("organization_id") is not None
            else actor.organization_id
            if actor is not None
            else ""
        ).strip()
        if not organization_id:
            return payload

        next_payload = dict(payload)
        raw_currency = next_payload.get("currency")
        has_explicit_currency = "currency" in next_payload

        if raw_currency is None or str(raw_currency).strip() == "":
            if not is_create and not has_explicit_currency:
                return next_payload

            default_currency_code = await self._get_default_organization_currency_code(organization_id)
            if default_currency_code is None:
                raise ValidationError("currency is required and organization has no active default currency")
            next_payload["currency"] = default_currency_code
            return next_payload

        normalized_currency = str(raw_currency).strip().upper()
        if not normalized_currency:
            raise ValidationError("currency is required")

        currency_repository = CurrencyRepository(self.repository.db)
        currency = await currency_repository.get_optional_by(
            filters={
                "organization_id": organization_id,
                "code": normalized_currency,
            }
        )
        if currency is None or currency.get("is_active") is False:
            raise ValidationError("currency is invalid")

        next_payload["currency"] = normalized_currency
        return next_payload

    @staticmethod
    def _actor_bypasses_organization_scope(actor: CurrentActor | None) -> bool:
        if actor is None:
            return True
        return "super_admin" in actor.roles

    @staticmethod
    def _actor_bypasses_department_scope(actor: CurrentActor | None) -> bool:
        if actor is None:
            return True
        privileged = {"super_admin", "admin", "manager"}
        return any(
            role in privileged or role.endswith("-manager")
            for role in actor.roles
        )

    def _uses_department_scope(self) -> bool:
        return self.repository.has_column("department_id")

    def _uses_warehouse_scope(self) -> bool:
        return self.repository.has_column("warehouse_id")

    @staticmethod
    def _actor_has_explicit_scope(actor: CurrentActor | None) -> bool:
        """True when the row-level scope feature has produced explicit allow-lists."""
        if actor is None:
            return False
        scope = getattr(actor, "scope", None)
        if scope is None:
            return False
        return (
            scope.allowed_department_ids is not None
            or scope.allowed_warehouse_ids is not None
        )

    @staticmethod
    def _is_empty_scope_value(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            normalized = value.strip().lower()
            return normalized in {"", "null", "none", "undefined"}
        return False

    def _is_required_column(self, column_name: str) -> bool:
        table = Base.metadata.tables.get(self.repository.table)
        if table is None or column_name not in table.columns:
            return False

        column = table.columns[column_name]
        has_default = (
            getattr(column, "default", None) is not None
            or getattr(column, "server_default", None) is not None
        )
        return not bool(column.nullable) and not has_default

    def _scope_filters_to_actor(
        self,
        filters: dict[str, Any] | None,
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any] | None:
        if actor is None or self._actor_bypasses_organization_scope(actor):
            return filters
        if not self.repository.has_column("organization_id"):
            return filters

        scoped_filters = dict(filters or {})
        scoped_organization_id = actor.organization_id
        existing_filter = scoped_filters.get("organization_id")

        if existing_filter is None:
            scoped_filters["organization_id"] = scoped_organization_id
        elif isinstance(existing_filter, (list, tuple, set)):
            scoped_filters["organization_id"] = [
                value for value in existing_filter if str(value) == scoped_organization_id
            ]
        elif str(existing_filter) != scoped_organization_id:
            scoped_filters["organization_id"] = []

        # Row-level scope (flag-gated): when explicit allow-lists are present,
        # delegate to UserScope which intersects with any caller-supplied
        # department/warehouse filter and returns an empty list for rows the
        # user cannot see. See docs/adr/0001-row-level-scope.md.
        if self._actor_has_explicit_scope(actor):
            return actor.scope.apply_filters(
                scoped_filters,
                has_department_column=self._uses_department_scope(),
                has_warehouse_column=self._uses_warehouse_scope(),
            )

        if not self._uses_department_scope():
            return scoped_filters
        if self._actor_bypasses_department_scope(actor):
            return scoped_filters

        scoped_department_id = (actor.department_id or "").strip()
        if not scoped_department_id:
            scoped_filters["department_id"] = []
            return scoped_filters

        existing_department_filter = scoped_filters.get("department_id")
        if existing_department_filter is None:
            scoped_filters["department_id"] = scoped_department_id
            return scoped_filters

        if isinstance(existing_department_filter, (list, tuple, set)):
            scoped_filters["department_id"] = [
                value for value in existing_department_filter if str(value) == scoped_department_id
            ]
            return scoped_filters

        if str(existing_department_filter) != scoped_department_id:
            scoped_filters["department_id"] = []
            return scoped_filters

        return scoped_filters

    def _apply_default_posting_status_on_create(self, data: dict[str, Any]) -> None:
        """User-facing creates on posting_status tables always land in 'draft'.

        Auto-sync services (auto-AR/AP) use the repository layer directly
        and never hit this hook — they snapshot via the DB's server_default
        of 'posted', which is the correct immutable state for shipment-driven
        rows.
        """
        if not self.repository.has_column("posting_status"):
            return
        data["posting_status"] = "draft"

    def _ensure_posting_mutable(self, entity: Mapping[str, Any]) -> None:
        """Block user-facing updates on rows whose posting_status is locked.

        Tables with a `posting_status` column (currently client_debts and
        supplier_debts) graduate rows from 'draft' to 'posted' when the
        underlying business event has happened. Posted rows are
        immutable — edits go through a reversal entry.

        Auto-sync services use the repository layer directly and therefore
        bypass this check, which matches the intent: shipment-driven
        upserts continue to track the parent's state; only manual
        user edits are locked.
        """
        if not self.repository.has_column("posting_status"):
            return
        status = str(entity.get("posting_status") or "").strip().lower()
        if status == "posted":
            raise ValidationError(
                "This record is posted and cannot be edited. Create a reversal entry instead."
            )

    def _ensure_actor_can_access_entity(
        self,
        entity: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> None:
        if actor is None or self._actor_bypasses_organization_scope(actor):
            return
        if not self.repository.has_column("organization_id"):
            return

        entity_organization_id = entity.get("organization_id")
        if entity_organization_id is None:
            return
        if str(entity_organization_id) != actor.organization_id:
            raise AccessDeniedError("You can only access records inside your organization")

        # Row-level scope path: check against explicit allow-lists.
        if self._actor_has_explicit_scope(actor):
            entity_department_id = entity.get("department_id")
            entity_warehouse_id = entity.get("warehouse_id")
            allowed = actor.scope.can_access(
                department_id=str(entity_department_id) if entity_department_id is not None else None,
                warehouse_id=str(entity_warehouse_id) if entity_warehouse_id is not None else None,
            )
            if not allowed:
                raise AccessDeniedError("You can only access records inside your scope")
            return

        if not self._uses_department_scope():
            return
        if self._actor_bypasses_department_scope(actor):
            return

        actor_department_id = (actor.department_id or "").strip()
        entity_department_id = entity.get("department_id")
        if entity_department_id is None:
            return
        if not actor_department_id or str(entity_department_id) != actor_department_id:
            raise AccessDeniedError("You can only access records inside your department")

    def _apply_actor_organization_on_create(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = self._normalize_uuid_payload_fields(payload, is_create=True)
        next_payload = self._normalize_temporal_payload_fields(next_payload, is_create=True)

        if self.repository.has_column("is_active"):
            active_value = next_payload.get("is_active")
            if active_value is None:
                next_payload["is_active"] = True

        if self.repository.has_column("organization_id"):
            current_value = next_payload.get("organization_id")
            if self._is_empty_scope_value(current_value):
                if actor is not None and actor.organization_id:
                    next_payload["organization_id"] = actor.organization_id
            elif (
                actor is not None
                and not self._actor_bypasses_organization_scope(actor)
                and str(current_value) != actor.organization_id
            ):
                raise AccessDeniedError("You can only create records inside your organization")

            if self._is_required_column("organization_id") and self._is_empty_scope_value(
                next_payload.get("organization_id")
            ):
                raise ValidationError("organization_id is required")

        if self._uses_department_scope():
            current_department_value = next_payload.get("department_id")
            if self._is_empty_scope_value(current_department_value):
                if actor is not None and actor.department_id:
                    next_payload["department_id"] = actor.department_id
            elif self._actor_has_explicit_scope(actor):
                if not actor.scope.can_access(department_id=str(current_department_value)):
                    raise AccessDeniedError(
                        "You cannot create records in that department",
                    )
            elif (
                actor is not None
                and not self._actor_bypasses_department_scope(actor)
                and actor.department_id
                and str(current_department_value) != actor.department_id
            ):
                next_payload["department_id"] = actor.department_id
                if self._uses_warehouse_scope() and "warehouse_id" in next_payload:
                    next_payload["warehouse_id"] = None

            if self._is_required_column("department_id") and self._is_empty_scope_value(
                next_payload.get("department_id")
            ):
                raise ValidationError("department_id is required")

        if self._uses_warehouse_scope() and self._actor_has_explicit_scope(actor):
            current_warehouse_value = next_payload.get("warehouse_id")
            if not self._is_empty_scope_value(current_warehouse_value):
                if not actor.scope.can_access(warehouse_id=str(current_warehouse_value)):
                    raise AccessDeniedError(
                        "You cannot create records in that warehouse",
                    )

        return next_payload

    def _apply_actor_organization_on_update(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = self._normalize_uuid_payload_fields(payload, is_create=False)
        next_payload = self._normalize_temporal_payload_fields(next_payload, is_create=False)
        if actor is None or self._actor_bypasses_organization_scope(actor):
            pass
        elif self.repository.has_column("organization_id"):
            if "organization_id" in next_payload:
                if next_payload["organization_id"] is None or str(next_payload["organization_id"]) != actor.organization_id:
                    raise AccessDeniedError("You cannot move records outside your organization")

        if (
            actor is not None
            and self._actor_has_explicit_scope(actor)
            and self._uses_department_scope()
            and "department_id" in next_payload
        ):
            new_dept = next_payload["department_id"]
            if new_dept is None or not actor.scope.can_access(department_id=str(new_dept)):
                raise AccessDeniedError("You cannot move records outside your scope")
        elif (
            actor is not None
            and not self._actor_bypasses_department_scope(actor)
            and self._uses_department_scope()
            and "department_id" in next_payload
        ):
            if next_payload["department_id"] is None or str(next_payload["department_id"]) != str(actor.department_id):
                raise AccessDeniedError("You cannot move records outside your department")

        if (
            actor is not None
            and self._actor_has_explicit_scope(actor)
            and self._uses_warehouse_scope()
            and "warehouse_id" in next_payload
            and next_payload["warehouse_id"] is not None
        ):
            if not actor.scope.can_access(warehouse_id=str(next_payload["warehouse_id"])):
                raise AccessDeniedError("You cannot move records outside your warehouse scope")

        return next_payload

    async def get_by_id(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        return Result.ok_result(self._map_read(entity))

    async def get_by_id_or_none(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[Any | None]:
        entity = await self.repository.get_by_id_optional(entity_id)
        if entity is None:
            return Result.ok_result(None)
        return Result.ok_result(self._map_read(entity))

    async def get_one_by(self, filters: dict[str, Any], order_by: str | None = None) -> Result[Any]:
        entity = await self.repository.get_one_by(filters=filters, order_by=order_by)
        return Result.ok_result(self._map_read(entity))

    async def get_one_by_or_none(
        self,
        filters: dict[str, Any],
        order_by: str | None = None,
    ) -> Result[Any | None]:
        entity = await self.repository.get_optional_by(filters=filters, order_by=order_by)
        if entity is None:
            return Result.ok_result(None)
        return Result.ok_result(self._map_read(entity))

    async def list(self, *args: Any, **kwargs: Any) -> Result[list[Any]]:
        rows = await self.repository.list(*args, **kwargs)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def get_scalar(
        self,
        column: str,
        filters: dict[str, Any] | None = None,
    ) -> Result[Any | None]:
        value = await self.repository.get_scalar(column=column, filters=filters)
        return Result.ok_result(value)

    async def pluck(
        self,
        column: str,
        filters: dict[str, Any] | None = None,
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Result[list[Any]]:
        rows = await self.repository.pluck(
            column=column,
            filters=filters,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return Result.ok_result(rows)

    async def get_by_ids(
        self,
        ids: Sequence[Any],
        order_by: str | None = None,
        limit: int | None = None,
        offset: int | None = None,
    ) -> Result[list[Any]]:
        rows = await self.repository.get_by_ids(
            ids=ids,
            order_by=order_by,
            limit=limit,
            offset=offset,
        )
        return Result.ok_result([self._map_read(row) for row in rows])

    async def list_with_pagination(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
        actor: CurrentActor | None = None,
    ) -> Result[dict[str, Any]]:
        scoped_filters = self._scope_filters_to_actor(filters, actor=actor)
        search_columns = self.get_searchable_columns()
        items = await self.repository.list(
            filters=scoped_filters,
            search=search,
            search_columns=search_columns,
            limit=limit,
            offset=offset,
            order_by=order_by,
        )
        total = await self.repository.count(
            filters=scoped_filters,
            search=search,
            search_columns=search_columns,
        )
        return Result.ok_result(
            {
                "items": [self._map_read(item) for item in items],
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": (offset + len(items)) < total,
            }
        )

    async def count(self, *args: Any, **kwargs: Any) -> int:
        return await self.repository.count(*args, **kwargs)

    async def exists(self, *args: Any, **kwargs: Any) -> bool:
        return await self.repository.exists(*args, **kwargs)

    async def exists_by_id(self, entity_id: Any) -> bool:
        return await self.repository.exists_by_id(entity_id)

    async def create(self, payload: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        data = self._apply_actor_organization_on_create(data, actor=actor)
        data = await self._auto_resolve_measurement_unit(data, existing=None)
        data = self._prepare_create_payload(data, actor=actor)
        data = await self._validate_catalog_fields(data, actor=actor, existing=None, is_create=True)
        self._apply_default_posting_status_on_create(data)
        async with self.repository.db.transaction():
            data = await self._before_create(data, actor=actor)
            entity = await self.repository.create(data)
            await self._after_create(entity, actor=actor)
            after_snapshot = await self._capture_audit_snapshot(
                entity.get(self.repository.id_column),
                entity=entity,
                actor=actor,
            )
            await self._record_audit_event(
                action="create",
                entity_id=entity.get(self.repository.id_column),
                before_data=None,
                after_data=after_snapshot,
                actor=actor,
            )
            await enqueue_operational_admin_alert(
                action="create",
                entity_table=self.repository.table,
                entity_id=str(entity.get(self.repository.id_column)),
                actor_username=(actor.username if actor is not None else None),
                before_data=None,
                after_data=after_snapshot,
            )
        return Result.ok_result(self._map_read(entity))

    async def create_many_safe(self, payloads: list[Any]) -> Result[list[Any]]:
        try:
            return await self.create_many(payloads)
        except ValidationError as error:
            return Result.err(str(error))

    async def create_many(self, payloads: list[Any]) -> Result[list[Any]]:
        entities = [self._payload_to_dict(payload) for payload in payloads]
        rows = await self.repository.create_many(entities)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def create_many_bulk(self, payloads: list[Any]) -> Result[list[Any]]:
        entities = [self._payload_to_dict(payload) for payload in payloads]
        rows = await self.repository.create_many_bulk(entities)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def upsert_many(
        self,
        payloads: list[Any],
        conflict_columns: list[str] | tuple[str, ...] | str,
        update_columns: list[str] | tuple[str, ...] | None = None,
        do_nothing: bool = False,
    ) -> Result[list[Any]]:
        entities = [self._payload_to_dict(payload) for payload in payloads]
        rows = await self.repository.upsert_many(
            payloads=entities,
            conflict_columns=conflict_columns,
            update_columns=update_columns,
            do_nothing=do_nothing,
        )
        return Result.ok_result([self._map_read(row) for row in rows])

    async def upsert_many_safe(
        self,
        payloads: list[Any],
        conflict_columns: list[str] | tuple[str, ...] | str,
        update_columns: list[str] | tuple[str, ...] | None = None,
        do_nothing: bool = False,
    ) -> Result[list[Any]]:
        try:
            return await self.upsert_many(
                payloads=payloads,
                conflict_columns=conflict_columns,
                update_columns=update_columns,
                do_nothing=do_nothing,
            )
        except ValidationError as error:
            return Result.err(str(error))

    async def update(self, entity_id: Any, payload: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        data = self._prepare_update_payload(data, actor=actor)
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            self._ensure_posting_mutable(existing)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=existing,
                actor=actor,
            )
            data = self._apply_actor_organization_on_update(data, actor=actor)
            data = await self._auto_resolve_measurement_unit(data, existing=existing)
            data = await self._validate_catalog_fields(data, actor=actor, existing=existing, is_create=False)
            data = await self._before_update(entity_id, data, existing=existing, actor=actor)
            entity = await self.repository.update_by_id(entity_id, data)
            await self._after_update(before=existing, after=entity, actor=actor)
            after_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=entity,
                actor=actor,
            )
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(entity))

    async def acknowledge_shipment(
        self,
        entity_id: Any,
        *,
        received_quantity: Any,
        note: str | None = None,
        actor: "CurrentActor | None" = None,
    ) -> Result[Any]:
        """Mark a shipment as received by the destination department.

        Works on any service whose table carries the transfer-ack columns
        (`status`, `acknowledged_at`, `acknowledged_by`, `received_quantity`).
        Sets status to 'received' on exact match, 'discrepancy' otherwise.
        """
        if not self.repository.has_column("status") or not self.repository.has_column("acknowledged_at"):
            raise ValidationError("This entity does not support acknowledgment")

        import decimal
        from datetime import datetime, timezone

        try:
            received = decimal.Decimal(str(received_quantity))
        except (decimal.InvalidOperation, ValueError, TypeError) as exc:
            raise ValidationError("received_quantity must be a number") from exc
        if received < 0:
            raise ValidationError("received_quantity must be non-negative")

        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)

            shipped_quantity_col = None
            for candidate in ("eggs_count", "chicks_count", "birds_count", "quantity"):
                if self.repository.has_column(candidate) and candidate in existing:
                    shipped_quantity_col = candidate
                    break
            if shipped_quantity_col is None:
                raise ValidationError("Cannot resolve shipped quantity column")

            shipped_quantity = decimal.Decimal(str(existing.get(shipped_quantity_col) or 0))
            status = "received" if received == shipped_quantity else "discrepancy"

            actor_employee_id = None
            if actor is not None and getattr(actor, "employee_id", None) is not None:
                actor_employee_id = str(actor.employee_id)

            payload: dict[str, Any] = {
                "status": status,
                "acknowledged_at": datetime.now(timezone.utc),
                "acknowledged_by": actor_employee_id,
                "received_quantity": str(received),
            }
            if note is not None:
                if self.repository.has_column("note"):
                    existing_note = str(existing.get("note") or "").strip()
                    note_suffix = f"[ack]: {note}".strip()
                    payload["note"] = f"{existing_note}\n{note_suffix}".strip() if existing_note else note_suffix

            entity = await self.repository.update_by_id(entity_id, payload)
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=self._normalize_audit_snapshot(existing),
                after_data=self._normalize_audit_snapshot(entity),
                actor=actor,
            )
        return Result.ok_result(self._map_read(entity))

    async def update_by_ids(self, ids: Sequence[Any], payload: Any) -> Result[list[Any]]:
        data = self._payload_to_dict(payload)
        rows = await self.repository.update_by_ids(ids=ids, payload=data)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def update_by_filters(self, filters: dict[str, Any], payload: Any) -> Result[list[Any]]:
        data = self._payload_to_dict(payload)
        rows = await self.repository.update_by_filters(filters=filters, payload=data)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def increment_by_filters(
        self,
        filters: dict[str, Any],
        payload: dict[str, int | float],
    ) -> Result[list[Any]]:
        rows = await self.repository.increment_by_filters(filters=filters, increments=payload)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def increment_by_id(
        self,
        entity_id: Any,
        payload: dict[str, int | float],
    ) -> Result[Any]:
        row = await self.repository.increment_by_id(entity_id=entity_id, increments=payload)
        return Result.ok_result(self._map_read(row))

    async def decrement_by_filters(
        self,
        filters: dict[str, Any],
        payload: dict[str, int | float],
    ) -> Result[list[Any]]:
        rows = await self.repository.decrement_by_filters(filters=filters, decrements=payload)
        return Result.ok_result([self._map_read(row) for row in rows])

    async def decrement_by_id(
        self,
        entity_id: Any,
        payload: dict[str, int | float],
    ) -> Result[Any]:
        row = await self.repository.decrement_by_id(entity_id=entity_id, decrements=payload)
        return Result.ok_result(self._map_read(row))

    async def upsert(
        self,
        payload: Any,
        conflict_columns: list[str] | tuple[str, ...] | str,
        update_columns: list[str] | tuple[str, ...] | None = None,
        do_nothing: bool = False,
    ) -> Result[Any]:
        data = self._payload_to_dict(payload)
        entity = await self.repository.upsert(
            payload=data,
            conflict_columns=conflict_columns,
            update_columns=update_columns,
            do_nothing=do_nothing,
        )
        return Result.ok_result(self._map_read(entity))

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[bool]:
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            self._ensure_posting_mutable(existing)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=existing,
                actor=actor,
            )
            deleted = await self.repository.delete_by_id(entity_id)
            if deleted:
                await self._after_delete(
                    deleted_entity=existing,
                    actor=actor,
                )
                await self._record_audit_event(
                    action="delete",
                    entity_id=entity_id,
                    before_data=before_snapshot,
                    after_data=None,
                    actor=actor,
                )
                await enqueue_operational_admin_alert(
                    action="delete",
                    entity_table=self.repository.table,
                    entity_id=str(entity_id),
                    actor_username=(actor.username if actor is not None else None),
                    before_data=before_snapshot,
                    after_data=None,
                )
        return Result.ok_result(deleted)

    async def delete_by_ids(self, ids: Sequence[Any]) -> Result[int]:
        return Result.ok_result(await self.repository.delete_by_ids(ids))

    async def delete_by_ids_safe(self, ids: Sequence[Any]) -> Result[int]:
        try:
            return await self.delete_by_ids(ids)
        except ValidationError as error:
            return Result.err(str(error))

    async def delete_many(self, filters: dict[str, Any]) -> Result[int]:
        deleted = await self.repository.delete_by_filters(filters)
        return Result.ok_result(deleted)

    async def delete_safe(self, entity_id: Any) -> Result[bool]:
        try:
            return await self.delete(entity_id)
        except NotFoundError as error:
            return Result.err(str(error))

    async def get_safe(self, entity_id: Any) -> Result[Any]:
        try:
            return await self.get_by_id(entity_id)
        except NotFoundError as error:
            return Result.err(str(error))

    async def create_safe(self, payload: Any) -> Result[Any]:
        try:
            return await self.create(payload)
        except ValidationError as error:
            return Result.err(str(error))

    async def update_safe(self, entity_id: Any, payload: Any) -> Result[Any]:
        try:
            return await self.update(entity_id, payload)
        except (ValidationError, NotFoundError) as error:
            return Result.err(str(error))


class CreatedByActorMixin:
    created_by_field = "created_by"

    def _prepare_create_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        if actor is not None:
            next_payload[self.created_by_field] = actor.employee_id
        return super()._prepare_create_payload(next_payload, actor=actor)
