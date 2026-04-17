from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Mapping
from uuid import uuid4

from app.core.exceptions import AccessDeniedError, ValidationError
from app.repositories.core import ClientDebtRepository
from app.repositories.egg import (
    EggMonthlyAnalyticsRepository,
    EggProductionRepository,
    EggQualityCheckRepository,
    EggShipmentRepository,
)
from app.repositories.hr import EmployeeRepository
from app.repositories.inventory import StockMovementRepository
from app.schemas.egg import (
    EggMonthlyAnalyticsReadSchema,
    EggProductionReadSchema,
    EggQualityCheckReadSchema,
    EggShipmentReadSchema,
)
from app.services.base import BaseService
from app.services.inventory import StockLedgerService, StockMovementDraft


EGG_QUALITY_CHECK_STATUSES = ("pending", "passed", "failed")
EGG_QUALITY_CHECK_GRADES = ("large", "medium", "small", "defective", "mixed")

AUTO_EGG_SHIPMENT_AR_MARKER_PREFIX = "[auto-egg-shipment-ar:"


def _build_auto_ar_marker(shipment_id: str) -> str:
    return f"{AUTO_EGG_SHIPMENT_AR_MARKER_PREFIX}{shipment_id}]"


def _compose_auto_debt_note(marker: str, source_note: Any) -> str:
    note_text = str(source_note).strip() if source_note is not None else ""
    if not note_text:
        return marker
    if marker in note_text:
        return note_text
    return f"{note_text}\n{marker}"


def _resolve_auto_debt_status(amount_total: Decimal, amount_paid: Decimal) -> str:
    if amount_paid <= Decimal("0"):
        return "open"
    if amount_paid >= amount_total:
        return "closed"
    return "partially_paid"


def _as_date(raw_value: object) -> date:
    if isinstance(raw_value, date):
        return raw_value
    return date.fromisoformat(str(raw_value))


def _as_decimal(raw_value: object) -> Decimal:
    return Decimal(str(raw_value or 0))


def _egg_key(production_id: str) -> str:
    return f"egg:{production_id}"


class EggProductionService(BaseService):
    read_schema = EggProductionReadSchema

    def __init__(self, repository: EggProductionRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _net_eggs(entity: Mapping[str, Any]) -> Decimal:
        eggs_collected = _as_decimal(entity.get("eggs_collected"))
        eggs_broken = _as_decimal(entity.get("eggs_broken"))
        eggs_rejected = _as_decimal(entity.get("eggs_rejected"))
        net = eggs_collected - eggs_broken - eggs_rejected
        if net <= 0:
            return Decimal("0")
        return net

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        quantity = self._net_eggs(entity)
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        movements: list[StockMovementDraft] = []
        if quantity > 0:
            movements.append(
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="egg",
                    item_key=_egg_key(str(entity["id"])),
                    movement_kind="incoming",
                    quantity=quantity,
                    unit="pcs",
                    occurred_on=_as_date(entity["produced_on"]),
                    reference_table="egg_production",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("note")) if entity.get("note") is not None else None),
                )
            )

        await ledger.replace_reference_movements(
            reference_table="egg_production",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="egg_production",
            reference_id=str(deleted_entity["id"]),
        )


class EggShipmentService(BaseService):
    read_schema = EggShipmentReadSchema

    def __init__(self, repository: EggShipmentRepository) -> None:
        super().__init__(repository=repository)

    async def _ensure_quality_passed(self, production_id: str) -> None:
        qc_repo = EggQualityCheckRepository(self.repository.db)
        latest = await qc_repo.get_optional_by(
            filters={"production_id": production_id},
            order_by=("checked_on desc", "created_at desc"),
        )
        if latest is None:
            raise ValidationError(
                "Shipment blocked: egg production has no quality check yet",
            )
        status = str(latest.get("status") or "").strip().lower()
        if status != "passed":
            raise ValidationError(
                f"Shipment blocked: latest quality check status is '{status}' (must be 'passed')",
            )

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        if data.get("production_id") is None:
            raise ValidationError("production_id is required for egg shipment")
        await self._ensure_quality_passed(str(data["production_id"]))
        return data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "production_id" in data and data.get("production_id") is None:
            raise ValidationError("production_id is required for egg shipment")
        production_id = data.get("production_id") or existing.get("production_id")
        if production_id is not None:
            await self._ensure_quality_passed(str(production_id))
        return data

    async def _sync_stock(self, entity: Mapping[str, Any]) -> None:
        production_id = entity.get("production_id")
        if production_id is None:
            return

        quantity = _as_decimal(entity.get("eggs_count"))
        if quantity <= 0:
            movements: list[StockMovementDraft] = []
        else:
            movements = [
                StockMovementDraft(
                    organization_id=str(entity["organization_id"]),
                    department_id=str(entity["department_id"]),
                    item_type="egg",
                    item_key=_egg_key(str(production_id)),
                    movement_kind="outgoing",
                    quantity=quantity,
                    unit=str(entity.get("unit") or "pcs"),
                    occurred_on=_as_date(entity["shipped_on"]),
                    reference_table="egg_shipments",
                    reference_id=str(entity["id"]),
                    warehouse_id=str(entity["warehouse_id"]) if entity.get("warehouse_id") else None,
                    note=(str(entity.get("invoice_no")) if entity.get("invoice_no") is not None else None),
                )
            ]

        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.replace_reference_movements(
            reference_table="egg_shipments",
            reference_id=str(entity["id"]),
            movements=movements,
        )

    async def _find_auto_ar_debt(self, shipment_id: str) -> dict[str, Any] | None:
        marker = _build_auto_ar_marker(shipment_id)
        row = await self.repository.db.fetchrow(
            """
            SELECT *
            FROM client_debts
            WHERE note LIKE $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            f"%{marker}%",
        )
        return dict(row) if row is not None else None

    async def _sync_auto_ar(self, entity: Mapping[str, Any]) -> None:
        shipment_id = str(entity["id"])
        unit_price = entity.get("unit_price")
        quantity = _as_decimal(entity.get("eggs_count"))
        debt_repo = ClientDebtRepository(self.repository.db)
        existing_debt = await self._find_auto_ar_debt(shipment_id)

        if unit_price is None or Decimal(str(unit_price or 0)) <= 0 or quantity <= 0:
            if existing_debt is not None:
                await debt_repo.delete_by_id(str(existing_debt["id"]))
            return

        unit_price_decimal = Decimal(str(unit_price)).quantize(Decimal("0.01"))
        amount_total = (unit_price_decimal * quantity).quantize(Decimal("0.01"))
        amount_paid = Decimal(str((existing_debt or {}).get("amount_paid") or 0)).quantize(Decimal("0.01"))
        if amount_paid > amount_total:
            raise ValidationError(
                "Cannot reduce shipment total below already recorded debt payments",
            )

        marker = _build_auto_ar_marker(shipment_id)
        note = _compose_auto_debt_note(
            marker,
            (existing_debt or {}).get("note") if existing_debt else None,
        )
        status = _resolve_auto_debt_status(amount_total, amount_paid)
        issued_on = _as_date(entity["shipped_on"])

        payload: dict[str, Any] = {
            "organization_id": str(entity["organization_id"]),
            "department_id": str(entity["department_id"]),
            "client_id": str(entity["client_id"]),
            "item_type": "egg",
            "item_key": f"egg_shipment:{shipment_id}",
            "quantity": str(quantity),
            "unit": str(entity.get("unit") or "pcs"),
            "amount_total": str(amount_total),
            "amount_paid": str(amount_paid),
            "currency": str(entity.get("currency") or ""),
            "issued_on": issued_on,
            "status": status,
            "note": note,
            "is_active": True,
        }

        if existing_debt is None:
            await debt_repo.create({"id": str(uuid4()), **payload})
        else:
            await debt_repo.update_by_id(str(existing_debt["id"]), payload)

    async def _delete_auto_ar(self, shipment_id: str) -> None:
        existing_debt = await self._find_auto_ar_debt(shipment_id)
        if existing_debt is None:
            return
        await ClientDebtRepository(self.repository.db).delete_by_id(str(existing_debt["id"]))

    async def _after_create(
        self,
        entity: Mapping[str, Any],
        *,
        actor=None,
    ) -> None:
        await self._sync_stock(entity)
        await self._sync_auto_ar(entity)

    async def _after_update(
        self,
        *,
        before: Mapping[str, Any],
        after: Mapping[str, Any],
        actor=None,
    ) -> None:
        await self._sync_stock(after)
        await self._sync_auto_ar(after)

    async def _after_delete(
        self,
        *,
        deleted_entity: Mapping[str, Any],
        actor=None,
    ) -> None:
        ledger = StockLedgerService(StockMovementRepository(self.repository.db))
        await ledger.clear_reference_movements(
            reference_table="egg_shipments",
            reference_id=str(deleted_entity["id"]),
        )
        await self._delete_auto_ar(str(deleted_entity["id"]))


class EggQualityCheckService(BaseService):
    read_schema = EggQualityCheckReadSchema

    def __init__(self, repository: EggQualityCheckRepository) -> None:
        super().__init__(repository=repository)

    async def _resolve_fields(
        self,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing) if existing is not None else {}
        merged.update(data)
        out: dict[str, Any] = dict(data)

        production_id_raw = merged.get("production_id")
        if not production_id_raw:
            raise ValidationError("production_id is required")
        production_id = str(production_id_raw)

        production_repo = EggProductionRepository(self.repository.db)
        production = await production_repo.get_by_id_optional(production_id)
        if production is None:
            raise ValidationError("production_id not found")

        organization_id = str(merged.get("organization_id") or production.get("organization_id"))
        if existing is None:
            out["organization_id"] = organization_id
        if str(production.get("organization_id")) != organization_id:
            raise AccessDeniedError("egg production belongs to another organization")

        department_id = merged.get("department_id")
        if not department_id:
            department_id = production.get("department_id")
            if department_id is None:
                raise ValidationError("department_id is required")
            out["department_id"] = str(department_id)
        elif str(department_id) != str(production.get("department_id")):
            raise ValidationError("department_id must match egg production department")

        out["production_id"] = production_id

        status_raw = merged.get("status")
        status = (str(status_raw).strip().lower() if status_raw else "pending") or "pending"
        if status not in EGG_QUALITY_CHECK_STATUSES:
            raise ValidationError(
                f"status must be one of: {', '.join(EGG_QUALITY_CHECK_STATUSES)}",
            )
        out["status"] = status

        grade_raw = merged.get("grade")
        if grade_raw:
            grade = str(grade_raw).strip().lower()
            if grade not in EGG_QUALITY_CHECK_GRADES:
                raise ValidationError(
                    f"grade must be one of: {', '.join(EGG_QUALITY_CHECK_GRADES)}",
                )
            out["grade"] = grade
        elif "grade" in data:
            out["grade"] = None

        inspector_id = merged.get("inspector_id")
        if inspector_id:
            employee_repo = EmployeeRepository(self.repository.db)
            inspector = await employee_repo.get_by_id_optional(str(inspector_id))
            if inspector is None:
                raise ValidationError("inspector_id not found")
            if str(inspector.get("organization_id")) != organization_id:
                raise AccessDeniedError("inspector belongs to another organization")
            out["inspector_id"] = str(inspector_id)
        elif "inspector_id" in data:
            out["inspector_id"] = None

        if existing is None and not merged.get("checked_on"):
            raise ValidationError("checked_on is required")

        return out

    async def _before_create(self, data: dict[str, Any], *, actor=None) -> dict[str, Any]:
        return await self._resolve_fields(data, existing=None)

    async def _before_update(
        self,
        entity_id,
        data: dict[str, Any],
        *,
        existing: Mapping[str, Any],
        actor=None,
    ) -> dict[str, Any]:
        if "organization_id" in data and str(data["organization_id"]) != str(existing.get("organization_id")):
            raise ValidationError("organization_id cannot be changed")
        if "department_id" in data and str(data["department_id"]) != str(existing.get("department_id")):
            raise ValidationError("department_id cannot be changed")
        if "production_id" in data and str(data["production_id"]) != str(existing.get("production_id")):
            raise ValidationError("production_id cannot be changed")
        return await self._resolve_fields(data, existing=existing)


class EggMonthlyAnalyticsService(BaseService):
    read_schema = EggMonthlyAnalyticsReadSchema

    def __init__(self, repository: EggMonthlyAnalyticsRepository) -> None:
        super().__init__(repository=repository)


__all__ = [
    "EggProductionService",
    "EggShipmentService",
    "EggQualityCheckService",
    "EggMonthlyAnalyticsService",
]
