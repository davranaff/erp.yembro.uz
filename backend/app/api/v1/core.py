from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.api.deps import (
    CurrentActor,
    db_dependency,
    get_current_actor,
    require_access,
    require_department_management_access,
)
from app.db.pool import Database
from app.repositories.core import (
    ClientDebtRepository,
    ClientRepository,
    CurrencyExchangeRateRepository,
    CurrencyRepository,
    DepartmentModuleRepository,
    DepartmentRepository,
    OrganizationRepository,
    ClientCategoryRepository,
    MeasurementUnitRepository,
    PoultryTypeRepository,
    WarehouseRepository,
)
from app.services.client_notifications import (
    SUPPORTED_TEMPLATE_KEYS,
    TelegramNotificationGateway,
    fetch_client_notification_context,
    resolve_template_message,
)
from app.services.core import (
    ClientDebtService,
    ClientService,
    CurrencyService,
    DepartmentModuleService,
    DepartmentService,
    ClientCategoryService,
    OrganizationService,
    MeasurementUnitService,
    PoultryTypeService,
    WarehouseService,
)
from app.services.exchange_rate import (
    CurrencyExchangeRateService,
    resolve_exchange_rate as _resolve_exchange_rate,
)


router = APIRouter(prefix="/core", tags=["core"])


class ClientNotificationSendPayload(BaseModel):
    template_key: str = Field(default="debt_reminder", max_length=64)
    message: str | None = Field(default=None, max_length=4000)
    channel: str = Field(default="telegram", max_length=24)
    department_id: str | None = Field(default=None, max_length=64)


class ClientNotificationBulkPayload(BaseModel):
    client_ids: list[str] = Field(default_factory=list)
    template_key: str = Field(default="debt_reminder", max_length=64)
    message: str | None = Field(default=None, max_length=4000)
    channel: str = Field(default="telegram", max_length=24)
    department_id: str | None = Field(default=None, max_length=64)


async def _send_client_notification(
    *,
    db: Database,
    actor: CurrentActor,
    client_id: str,
    template_key: str,
    custom_message: str | None,
    channel: str,
    department_id: str | None,
    gateway: TelegramNotificationGateway,
) -> dict[str, Any]:
    context = await fetch_client_notification_context(
        db=db,
        actor_organization_id=actor.organization_id,
        client_id=client_id,
        department_id=department_id,
    )
    if context is None:
        return {
            "client_id": client_id,
            "template_key": template_key,
            "channel": channel,
            "sent": False,
            "error": "Client not found",
        }

    templates = context.get("templates") if isinstance(context.get("templates"), list) else []
    message = resolve_template_message(
        template_key=template_key,
        templates=templates,
        custom_message=custom_message,
    )
    if not message:
        return {
            "client_id": client_id,
            "template_key": template_key,
            "channel": channel,
            "sent": False,
            "error": "Message is empty",
        }

    normalized_channel = str(channel or "").strip().lower()
    if normalized_channel != "telegram":
        return {
            "client_id": client_id,
            "template_key": template_key,
            "channel": normalized_channel,
            "sent": False,
            "error": "Only telegram channel is currently supported",
        }

    client_payload = context.get("client") if isinstance(context.get("client"), dict) else {}
    chat_id = str(client_payload.get("telegram_chat_id") or "").strip()
    if not chat_id:
        return {
            "client_id": client_id,
            "template_key": template_key,
            "channel": normalized_channel,
            "sent": False,
            "error": "Client telegram_chat_id is missing",
        }

    send_result = await gateway.send_message(chat_id=chat_id, text=message)
    return {
        "client_id": client_id,
        "template_key": template_key,
        "channel": normalized_channel,
        "sent": send_result.ok,
        "provider_message_id": send_result.provider_message_id,
        "error": send_result.error,
        "message": message,
    }


@router.get(
    "/visible-departments",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_actor)],
)
async def list_visible_departments(
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = DepartmentService(DepartmentRepository(db))
    result = await service.list_visible_to_actor(actor=current_actor)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Operation failed",
        )
    return result.data


@router.get(
    "/workspace-modules",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(get_current_actor)],
)
async def list_workspace_modules(
    db: Database = Depends(db_dependency),
    current_actor: CurrentActor = Depends(get_current_actor),
) -> dict[str, Any]:
    service = DepartmentModuleService(DepartmentModuleRepository(db))
    result = await service.list_workspace_modules(actor=current_actor)
    if not result.ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=result.error or "Operation failed",
        )
    return result.data


@router.get(
    "/clients/{client_id}/notification-context",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("client.read", roles=("admin", "manager")))],
)
async def get_client_notification_context(
    client_id: str,
    department_id: str | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    context = await fetch_client_notification_context(
        db=db,
        actor_organization_id=current_actor.organization_id,
        client_id=client_id,
        department_id=department_id,
    )
    if context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Client not found",
        )
    return context


@router.post(
    "/clients/{client_id}/notify",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("client.write", roles=("admin", "manager")))],
)
async def send_notification_to_client(
    client_id: str,
    payload: ClientNotificationSendPayload,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    gateway = TelegramNotificationGateway()
    result = await _send_client_notification(
        db=db,
        actor=current_actor,
        client_id=client_id,
        template_key=payload.template_key,
        custom_message=payload.message,
        channel=payload.channel,
        department_id=payload.department_id,
        gateway=gateway,
    )
    return result


@router.post(
    "/clients/notify/bulk",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("client.write", roles=("admin", "manager")))],
)
async def send_bulk_notifications(
    payload: ClientNotificationBulkPayload,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    normalized_client_ids = [
        str(client_id).strip()
        for client_id in payload.client_ids
        if str(client_id).strip()
    ]
    if not normalized_client_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="client_ids cannot be empty")

    normalized_template_key = str(payload.template_key or "").strip().lower()
    if normalized_template_key and normalized_template_key not in SUPPORTED_TEMPLATE_KEYS and not str(payload.message or "").strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="template_key is invalid")

    gateway = TelegramNotificationGateway()
    results: list[dict[str, Any]] = []
    for client_id in dict.fromkeys(normalized_client_ids):
        result = await _send_client_notification(
            db=db,
            actor=current_actor,
            client_id=client_id,
            template_key=normalized_template_key,
            custom_message=payload.message,
            channel=payload.channel,
            department_id=payload.department_id,
            gateway=gateway,
        )
        results.append(result)

    success_count = sum(1 for item in results if bool(item.get("sent")))
    failed_count = len(results) - success_count
    return {
        "total": len(results),
        "sent": success_count,
        "failed": failed_count,
        "items": results,
    }


# --- Currency exchange rate endpoints ---------------------------------------


class CurrencyExchangeRateSyncPayload(BaseModel):
    codes: list[str] | None = Field(default=None)


@router.post(
    "/currency-exchange-rates/sync",
    status_code=status.HTTP_200_OK,
    dependencies=[
        Depends(
            require_access(
                "currency_exchange_rate.write",
                roles=("admin", "manager"),
            )
        )
    ],
)
async def sync_currency_exchange_rates(
    payload: CurrencyExchangeRateSyncPayload | None = None,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    """Pull the latest CBU.uz rates for the caller's organization."""

    service = CurrencyExchangeRateService(CurrencyExchangeRateRepository(db))
    codes = list(payload.codes) if payload and payload.codes else None
    summary = await service.sync_from_cbu(
        organization_id=current_actor.organization_id,
        codes=codes,
    )
    return {"ok": True, **summary}


@router.get(
    "/currency-exchange-rates/latest",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("currency_exchange_rate.read"))],
)
async def latest_currency_exchange_rate(
    currency_id: str = Query(..., min_length=1),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = CurrencyExchangeRateService(CurrencyExchangeRateRepository(db))
    row = await service.get_latest_for_currency(
        organization_id=current_actor.organization_id,
        currency_id=currency_id,
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No exchange rate found for this currency",
        )
    return {
        "currency_id": str(row.get("currency_id")),
        "rate": str(row.get("rate")),
        "rate_date": (row.get("rate_date").isoformat() if row.get("rate_date") else None),
        "source": row.get("source"),
        "source_ref": row.get("source_ref"),
    }


@router.get(
    "/currency-exchange-rates/resolve",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("currency_exchange_rate.read"))],
)
async def resolve_currency_exchange_rate(
    currency_id: str = Query(..., min_length=1),
    on_date: str | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    """Return the rate that would be applied to a transaction on a given date.

    Useful for the frontend to preview "сколько будет в UZS" before the
    form is submitted.
    """

    from datetime import datetime as _datetime, date as _date

    if on_date:
        try:
            parsed_date = _datetime.strptime(on_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="on_date must be in YYYY-MM-DD format",
            )
    else:
        parsed_date = _date.today()

    resolved = await _resolve_exchange_rate(
        db,
        organization_id=current_actor.organization_id,
        currency_id=currency_id,
        on_date=parsed_date,
    )
    return {
        "currency_id": currency_id,
        "currency_code": resolved.currency_code,
        "rate": str(resolved.rate),
        "rate_date": resolved.rate_date.isoformat() if resolved.rate_date else None,
        "source": resolved.source,
        "is_base": resolved.is_base,
        "on_date": parsed_date.isoformat(),
    }


# CRUD router registered AFTER the custom routes so that `/latest`,
# `/sync`, `/resolve` are matched literally (otherwise they'd be eaten
# by the auto-generated `/{id}` routes).
router.include_router(
    build_crud_router(
        prefix="currency-exchange-rates",
        service_factory=lambda db: CurrencyExchangeRateService(
            CurrencyExchangeRateRepository(db)
        ),
        permission_prefix="currency_exchange_rate",
        tags=["currency-exchange-rate"],
    )
)


router.include_router(
    build_crud_router(
        prefix="organizations",
        service_factory=lambda db: OrganizationService(OrganizationRepository(db)),
        permission_prefix="organization",
        tags=["organization"],
    )
)

router.include_router(
    build_crud_router(
        prefix="department-modules",
        service_factory=lambda db: DepartmentModuleService(DepartmentModuleRepository(db)),
        permission_prefix="department_module",
        tags=["department-module"],
    )
)

router.include_router(
    build_crud_router(
        prefix="departments",
        service_factory=lambda db: DepartmentService(DepartmentRepository(db)),
        permission_prefix="department",
        tags=["department"],
        read_dependency=require_department_management_access("department.read", roles=("admin", "manager")),
        write_dependency=require_department_management_access("department.write", roles=("admin", "manager")),
        create_dependency=require_department_management_access("department.create", roles=("admin", "manager")),
        delete_dependency=require_department_management_access("department.delete", roles=("admin", "manager")),
    )
)

router.include_router(
    build_crud_router(
        prefix="warehouses",
        service_factory=lambda db: WarehouseService(WarehouseRepository(db)),
        permission_prefix="warehouse",
        tags=["warehouse"],
    )
)

router.include_router(
    build_crud_router(
        prefix="clients",
        service_factory=lambda db: ClientService(ClientRepository(db)),
        permission_prefix="client",
        tags=["client"],
    )
)

router.include_router(
    build_crud_router(
        prefix="client-debts",
        service_factory=lambda db: ClientDebtService(ClientDebtRepository(db)),
        permission_prefix="client_debt",
        tags=["client-debt"],
    )
)

router.include_router(
    build_crud_router(
        prefix="currencies",
        service_factory=lambda db: CurrencyService(CurrencyRepository(db)),
        permission_prefix="currency",
        tags=["currency"],
    )
)

router.include_router(
    build_crud_router(
        prefix="poultry-types",
        service_factory=lambda db: PoultryTypeService(PoultryTypeRepository(db)),
        permission_prefix="poultry_type",
        tags=["poultry-type"],
    )
)

router.include_router(
    build_crud_router(
        prefix="measurement-units",
        service_factory=lambda db: MeasurementUnitService(MeasurementUnitRepository(db)),
        permission_prefix="measurement_unit",
        tags=["measurement-unit"],
    )
)

router.include_router(
    build_crud_router(
        prefix="client-categories",
        service_factory=lambda db: ClientCategoryService(ClientCategoryRepository(db)),
        permission_prefix="client_category",
        tags=["client-category"],
    )
)

register_module_stats_route(
    router,
    module="core",
    label="Core",
    tables=(
        ModuleStatsTable(key="organizations", label="Organizations", table="organizations"),
        ModuleStatsTable(key="department_modules", label="Department Modules", table="department_modules"),
        ModuleStatsTable(key="workspace_resources", label="Workspace Resources", table="workspace_resources"),
        ModuleStatsTable(key="departments", label="Departments", table="departments"),
        ModuleStatsTable(key="warehouses", label="Warehouses", table="warehouses"),
        ModuleStatsTable(key="clients", label="Clients", table="clients"),
        ModuleStatsTable(key="client_debts", label="Client Debts", table="client_debts"),
        ModuleStatsTable(key="currencies", label="Currencies", table="currencies"),
        ModuleStatsTable(key="poultry_types", label="Poultry Types", table="poultry_types"),
        ModuleStatsTable(key="measurement_units", label="Measurement Units", table="measurement_units"),
        ModuleStatsTable(key="client_categories", label="Client Categories", table="client_categories"),
    ),
)

__all__ = ["router"]
