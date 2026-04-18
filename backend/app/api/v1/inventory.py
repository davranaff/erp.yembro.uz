from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.crud import build_crud_router
from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.core.exceptions import ValidationError
from app.db.pool import Database
from app.repositories.core import WarehouseRepository
from app.repositories.inventory import (
    StockMovementRepository,
    StockReorderLevelRepository,
    StockTakeLineRepository,
    StockTakeRepository,
)
from app.services.inventory import (
    ITEM_TYPES,
    StockLedgerService,
    StockMovementService,
    StockReorderLevelService,
    StockTakeLineService,
    StockTakeService,
    normalize_stock_movement_unit,
)


router = APIRouter(prefix="/inventory", tags=["inventory"])

PRIVILEGED_SCOPE_ROLES = {"super_admin", "admin", "manager"}


router.include_router(
    build_crud_router(
        prefix="movements",
        service_factory=lambda db: StockMovementService(StockMovementRepository(db)),
        permission_prefix="stock_movement",
        tags=["stock-movement"],
    )
)

router.include_router(
    build_crud_router(
        prefix="stock-takes",
        service_factory=lambda db: StockTakeService(StockTakeRepository(db)),
        permission_prefix="stock_take",
        tags=["stock-take"],
    )
)

router.include_router(
    build_crud_router(
        prefix="stock-take-lines",
        service_factory=lambda db: StockTakeLineService(StockTakeLineRepository(db)),
        permission_prefix="stock_take",
        tags=["stock-take-line"],
    )
)

router.include_router(
    build_crud_router(
        prefix="reorder-levels",
        service_factory=lambda db: StockReorderLevelService(StockReorderLevelRepository(db)),
        permission_prefix="stock_reorder_level",
        tags=["stock-reorder-level"],
    )
)


def _can_override_department_scope(actor: CurrentActor) -> bool:
    return bool(PRIVILEGED_SCOPE_ROLES.intersection(actor.roles))


def _resolve_department_id(
    *,
    actor: CurrentActor,
    requested_department_id: str | None,
) -> str:
    if requested_department_id and _can_override_department_scope(actor):
        return requested_department_id

    if actor.department_id:
        return actor.department_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="department_id is required",
    )


def _resolve_optional_department_id(
    *,
    actor: CurrentActor,
    requested_department_id: str | None,
) -> str | None:
    normalized_requested = str(requested_department_id or "").strip() or None
    if normalized_requested and _can_override_department_scope(actor):
        return normalized_requested
    if actor.department_id:
        return actor.department_id
    return normalized_requested


@router.get(
    "/stock/balance",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("stock_movement.read", roles=("admin", "manager")))],
)
async def get_stock_balance(
    item_type: str = Query(..., pattern="^(egg|chick|feed|feed_raw|medicine|semi_product)$"),
    item_key: str | None = Query(default=None, min_length=2),
    as_of: date | None = Query(default=None),
    department_id: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    resolved_department_id = _resolve_optional_department_id(actor=current_actor, requested_department_id=department_id)
    resolved_warehouse_id = str(warehouse_id or "").strip() or None
    if resolved_warehouse_id and not _can_override_department_scope(current_actor) and current_actor.department_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="department_id is required",
        )

    warehouse_repository = WarehouseRepository(db)
    ledger_service = StockLedgerService(
        StockMovementRepository(db),
        warehouse_repository,
    )
    resolved_warehouse = await warehouse_repository.get_by_id_optional(resolved_warehouse_id) if resolved_warehouse_id else None
    effective_department_id = (
        resolved_department_id
        or (str(resolved_warehouse["department_id"]) if resolved_warehouse is not None else None)
    )
    effective_warehouse_id = str(resolved_warehouse["id"]) if resolved_warehouse is not None else resolved_warehouse_id
    if item_key:
        balance = await ledger_service.get_balance(
            organization_id=current_actor.organization_id,
            department_id=resolved_department_id,
            warehouse_id=resolved_warehouse_id,
            item_type=item_type,
            item_key=item_key,
            as_of=as_of,
        )
        return {
            "item_type": item_type,
            "item_key": item_key,
            "department_id": effective_department_id,
            "warehouse_id": effective_warehouse_id,
            "as_of": as_of,
            "balance": str(balance),
        }

    balances = await ledger_service.list_balances(
        organization_id=current_actor.organization_id,
        department_id=resolved_department_id,
        warehouse_id=resolved_warehouse_id,
        item_type=item_type,
        as_of=as_of,
    )
    return {
        "item_type": item_type,
        "department_id": effective_department_id,
        "warehouse_id": effective_warehouse_id,
        "as_of": as_of,
        "items": balances,
    }


@router.post(
    "/stock/transfer",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_access("stock_movement.create", roles=("admin", "manager")))],
)
async def create_internal_transfer(
    payload: dict[str, Any],
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    raw_item_type = str(payload.get("item_type") or "").strip().lower()
    if raw_item_type not in ITEM_TYPES:
        raise ValidationError("item_type must be one of: egg, chick, feed, feed_raw, medicine, semi_product")

    item_key = str(payload.get("item_key") or "").strip()
    if not item_key:
        raise ValidationError("item_key is required")

    raw_occurred_on = payload.get("occurred_on")
    if isinstance(raw_occurred_on, date):
        occurred_on = raw_occurred_on
    elif isinstance(raw_occurred_on, str):
        try:
            occurred_on = date.fromisoformat(raw_occurred_on)
        except ValueError as exc:
            raise ValidationError("occurred_on has an invalid value") from exc
    else:
        occurred_on = date.today()

    from_department_id = _resolve_optional_department_id(
        actor=current_actor,
        requested_department_id=(str(payload.get("from_department_id")) if payload.get("from_department_id") else None),
    )
    from_warehouse_id = str(payload.get("from_warehouse_id") or "").strip() or None
    to_warehouse_id = str(payload.get("to_warehouse_id") or "").strip() or None
    to_department_raw = str(payload.get("to_department_id") or "").strip() or None
    if not to_department_raw and not to_warehouse_id:
        raise ValidationError("to_department_id or to_warehouse_id is required")

    unit = normalize_stock_movement_unit(payload.get("unit"))
    try:
        quantity = Decimal(str(payload.get("quantity") or "0"))
    except Exception as exc:
        raise ValidationError("quantity has an invalid value") from exc
    note = payload.get("note")

    ledger_service = StockLedgerService(
        StockMovementRepository(db),
        WarehouseRepository(db),
    )
    async with db.transaction():
        transfer_payload = await ledger_service.transfer_between_departments(
            organization_id=current_actor.organization_id,
            item_type=raw_item_type,
            item_key=item_key,
            quantity=quantity,
            unit=unit,
            occurred_on=occurred_on,
            from_department_id=from_department_id,
            to_department_id=to_department_raw,
            from_warehouse_id=from_warehouse_id,
            to_warehouse_id=to_warehouse_id,
            note=(str(note) if note is not None else None),
        )

    return transfer_payload


@router.post(
    "/stock-takes/{stock_take_id}/finalize",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("stock_take.write", roles=("admin", "manager")))],
)
async def finalize_stock_take(
    stock_take_id: str,
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    service = StockTakeService(StockTakeRepository(db))
    return await service.finalize(stock_take_id, actor=current_actor)


@router.get(
    "/stock/low-stock",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_access("stock_reorder_level.read", roles=("admin", "manager")))],
)
async def list_low_stock(
    department_id: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    as_of: date | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    resolved_department_id = _resolve_optional_department_id(
        actor=current_actor,
        requested_department_id=department_id,
    )
    resolved_warehouse_id = str(warehouse_id or "").strip() or None

    service = StockReorderLevelService(StockReorderLevelRepository(db))
    items = await service.list_low_stock(
        organization_id=current_actor.organization_id,
        department_id=resolved_department_id,
        warehouse_id=resolved_warehouse_id,
        as_of=as_of,
    )
    return {
        "department_id": resolved_department_id,
        "warehouse_id": resolved_warehouse_id,
        "as_of": as_of,
        "items": items,
    }


__all__ = ["router"]
