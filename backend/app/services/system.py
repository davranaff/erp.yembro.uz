from __future__ import annotations

from datetime import datetime
import json
from typing import Any

from app.utils.result import Result
from app.schemas.system import AuditLogReadSchema
from app.services.base import BaseService


class AuditLogService(BaseService):
    read_schema = AuditLogReadSchema
    audit_enabled = False

    def _map_read(self, row: dict[str, Any]) -> Any:
        payload = dict(row)
        for field_name in (
            "actor_roles",
            "changed_fields",
            "before_data",
            "after_data",
            "context_data",
        ):
            value = payload.get(field_name)
            if not isinstance(value, str):
                continue
            try:
                payload[field_name] = json.loads(value)
            except ValueError:
                continue
        return super()._map_read(payload)

    async def list_entity_history(
        self,
        *,
        entity_table: str,
        entity_id: str,
        limit: int = 100,
        offset: int = 0,
        actor=None,
    ):
        return await self.list_with_pagination(
            filters={
                "entity_table": entity_table,
                "entity_id": entity_id,
            },
            limit=limit,
            offset=offset,
            order_by=("changed_at desc", "id desc"),
            actor=actor,
        )

    async def list_audit_feed(
        self,
        *,
        filters: dict[str, Any] | None = None,
        search: str | None = None,
        changed_from: datetime | None = None,
        changed_to: datetime | None = None,
        limit: int = 100,
        offset: int = 0,
        actor=None,
    ) -> Result[dict[str, Any]]:
        scoped_filters = self._scope_filters_to_actor(filters, actor=actor)
        search_columns = self.get_searchable_columns()
        items = await self.repository.list_filtered(
            filters=scoped_filters,
            search=search,
            search_columns=search_columns,
            changed_from=changed_from,
            changed_to=changed_to,
            limit=limit,
            offset=offset,
            order_by=("changed_at desc", "id desc"),
        )
        total = await self.repository.count_filtered(
            filters=scoped_filters,
            search=search,
            search_columns=search_columns,
            changed_from=changed_from,
            changed_to=changed_to,
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

    async def get_by_id(self, entity_id: Any, *, actor=None):
        return await super().get_by_id(entity_id, actor=actor)


__all__ = ["AuditLogService"]
