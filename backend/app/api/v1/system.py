from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.repositories.system import AuditLogRepository
from app.services.system import AuditLogService


router = APIRouter(prefix="/system", tags=["system"])


@router.get("/ping", status_code=status.HTTP_200_OK)
async def ping() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/audit",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("audit.read", roles=("admin", "manager")))],
)
async def list_audit_logs(
    entity_table: str | None = Query(default=None),
    entity_id: str | None = Query(default=None),
    action: str | None = Query(default=None),
    actor_id: str | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1),
    changed_from: datetime | None = Query(default=None),
    changed_to: datetime | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = AuditLogService(AuditLogRepository(db))
    filters = {
        key: value
        for key, value in {
            "entity_table": entity_table,
            "entity_id": entity_id,
            "action": action,
            "actor_id": actor_id,
        }.items()
        if value not in {None, ""}
    }
    result = await service.list_audit_feed(
        filters=filters or None,
        search=search,
        changed_from=changed_from,
        changed_to=changed_to,
        limit=limit,
        offset=offset,
        actor=current_actor,
    )
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Failed to load audit logs",
        )
    return result.data
