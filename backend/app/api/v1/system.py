from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.repositories.system import AuditLogRepository
from app.schemas.system import TelegramDeepLinkSchema
from app.services.system import AuditLogService
from app.services.telegram_bot import TelegramBotService


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


@router.post(
    "/telegram/deep-link",
    status_code=status.HTTP_200_OK,
)
async def create_telegram_deep_link(
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> TelegramDeepLinkSchema:
    service = TelegramBotService(db)
    try:
        payload = await service.generate_self_service_link(actor=current_actor)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return TelegramDeepLinkSchema.model_validate(payload)


@router.post(
    "/telegram/webhook",
    status_code=status.HTTP_200_OK,
)
async def telegram_webhook(
    payload: dict[str, Any],
    telegram_secret: str | None = Header(default=None, alias="X-Telegram-Bot-Api-Secret-Token"),
    db: Database = Depends(db_dependency),
) -> dict[str, bool]:
    service = TelegramBotService(db)
    try:
        await service.process_webhook_update(payload=payload, secret_token=telegram_secret)
    except PermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return {"ok": True}
