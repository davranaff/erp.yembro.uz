from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.schemas.base import BaseSchema, IDSchema


class AuditLogReadSchema(IDSchema):
    organization_id: UUID | None = None
    actor_id: UUID | None = None
    entity_table: str
    entity_id: str
    action: str
    actor_username: str | None = None
    actor_roles: list[str] | None = None
    changed_fields: list[str] | None = None
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    context_data: dict[str, Any] | None = None
    changed_at: datetime


class TelegramDeepLinkSchema(BaseSchema):
    url: str
    expires_at: datetime


class TelegramDeepLinkRequestSchema(BaseSchema):
    """Body for POST /system/telegram/deep-link.

    * target='self' (or omitted) — generate a link for the calling
      employee, exactly the same as before.
    * target='employee' + employee_id — admin generates a link on
      behalf of another employee (used by the invite action in the
      HR table).
    * target='client' + client_id — admin generates a link that
      binds a specific client's Telegram chat when followed.
    """

    target: str | None = None
    employee_id: UUID | None = None
    client_id: UUID | None = None


class TelegramBindingStatusSchema(BaseSchema):
    employees: dict[str, bool]
    clients: dict[str, bool]
