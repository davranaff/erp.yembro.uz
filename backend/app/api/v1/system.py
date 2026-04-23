from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.repositories.system import AuditLogRepository
from app.schemas.system import (
    TelegramBindingStatusSchema,
    TelegramDeepLinkRequestSchema,
    TelegramDeepLinkSchema,
)
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


def _require_admin_or_manager(actor: CurrentActor) -> None:
    roles = {role.lower() for role in actor.roles}
    if not roles & {"admin", "super_admin", "manager"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins or managers can invite others to the bot",
        )


@router.post(
    "/telegram/deep-link",
    status_code=status.HTTP_200_OK,
)
async def create_telegram_deep_link(
    payload: TelegramDeepLinkRequestSchema | None = None,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> TelegramDeepLinkSchema:
    service = TelegramBotService(db)
    target = (payload.target if payload else None) or "self"
    try:
        if target == "self":
            result = await service.generate_self_service_link(actor=current_actor)
        elif target == "employee":
            if payload is None or payload.employee_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="employee_id is required when target='employee'",
                )
            _require_admin_or_manager(current_actor)
            result = await service.generate_employee_link(
                actor=current_actor, employee_id=str(payload.employee_id)
            )
        elif target == "client":
            if payload is None or payload.client_id is None:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="client_id is required when target='client'",
                )
            _require_admin_or_manager(current_actor)
            result = await service.generate_client_link(
                actor=current_actor, client_id=str(payload.client_id)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown target '{target}'",
            )
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
    return TelegramDeepLinkSchema.model_validate(result)


@router.get(
    "/telegram/binding-status",
    status_code=status.HTTP_200_OK,
)
async def get_telegram_binding_status(
    employee_ids: list[str] | None = Query(default=None),
    client_ids: list[str] | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> TelegramBindingStatusSchema:
    service = TelegramBotService(db)
    result = await service.get_binding_status(
        organization_id=str(current_actor.organization_id),
        employee_ids=[value for value in (employee_ids or []) if value],
        client_ids=[value for value in (client_ids or []) if value],
    )
    return TelegramBindingStatusSchema.model_validate(result)


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


@router.post(
    "/telegram/webhook/register",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("system.manage", roles=("admin", "super_admin")))],
)
async def register_telegram_webhook(
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = TelegramBotService(db)
    try:
        result = await service.register_webhook()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return result


@router.delete(
    "/telegram/webhook",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("system.manage", roles=("admin", "super_admin")))],
)
async def delete_telegram_webhook(
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = TelegramBotService(db)
    try:
        result = await service.delete_webhook()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return result


@router.get(
    "/telegram/webhook/info",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("system.manage", roles=("admin", "super_admin")))],
)
async def get_telegram_webhook_info(
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = TelegramBotService(db)
    try:
        result = await service.get_webhook_info()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    return result
