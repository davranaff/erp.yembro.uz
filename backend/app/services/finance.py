from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from app.core.exceptions import ValidationError
from app.repositories.core import ClientDebtRepository, ClientRepository
from app.repositories.finance import (
    CashAccountRepository,
    CashTransactionRepository,
    DebtPaymentRepository,
    EmployeeAdvanceRepository,
    ExpenseCategoryRepository,
    ExpenseRepository,
    SupplierDebtRepository,
)
from app.schemas.finance import (
    CashAccountReadSchema,
    CashTransactionReadSchema,
    DebtPaymentReadSchema,
    EmployeeAdvanceReadSchema,
    ExpenseCategoryReadSchema,
    ExpenseReadSchema,
    SupplierDebtReadSchema,
)
from app.services.base import BaseService, CreatedByActorMixin
from app.services.inventory import (
    ITEM_KEY_REFERENCE_TABLE,
    ITEM_TYPES,
    _fetch_inventory_item_key_options,
    _inventory_item_key_exists,
    normalize_stock_movement_unit,
)
from app.utils.result import Result

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


DEBT_STATUSES = ("open", "partially_paid", "closed", "cancelled")
DEBT_PAYMENT_METHODS = ("cash", "bank", "card", "transfer", "offset", "other")
DEBT_PAYMENT_DIRECTIONS = ("incoming", "outgoing")
DEBT_PAYMENT_MARKER_PREFIX = "[auto-linked-debt-payment:"
AUTO_DEBT_CASH_TITLE_MAX_LEN = 255


ALLOWED_CASH_TRANSACTION_TYPES = (
    "income",
    "expense",
    "transfer_in",
    "transfer_out",
    "adjustment",
)
CASH_TRANSACTION_TYPE_OPTIONS: tuple[dict[str, str], ...] = (
    {"value": "income", "label": "Income"},
    {"value": "expense", "label": "Expense"},
    {"value": "transfer_in", "label": "Transfer in"},
    {"value": "transfer_out", "label": "Transfer out"},
    {"value": "adjustment", "label": "Adjustment"},
)
CASH_TRANSACTION_TYPE_ALIASES = {
    "income": "income",
    "incoming": "income",
    "in": "income",
    "expense": "expense",
    "outgoing": "expense",
    "out": "expense",
    "transfer_in": "transfer_in",
    "transferin": "transfer_in",
    "incoming_transfer": "transfer_in",
    "transfer_out": "transfer_out",
    "transferout": "transfer_out",
    "outgoing_transfer": "transfer_out",
    "adjustment": "adjustment",
    "adjust": "adjustment",
    "manual_adjustment": "adjustment",
}
AUTO_EXPENSE_MARKER_PREFIX = "[auto-linked-cash-transaction:"
AUTO_EXPENSE_CATEGORY_NAME = "Automatic cash expenses"
AUTO_EXPENSE_CATEGORY_DESCRIPTION = "Auto-created category for cash transaction expenses."
AUTO_EXPENSE_CATEGORY_CODE_PREFIX = "AUTO-CASH"
VIRTUAL_EXPENSE_CATEGORY_FIELD = "expense_category_id"
VIRTUAL_DEPARTMENT_FIELD = "department_id"


def _normalize_cash_transaction_type(raw_value: Any) -> str:
    value_text = str(raw_value or "").strip().lower()
    if not value_text:
        raise ValidationError("transaction_type is required")

    compact_value = "_".join(value_text.replace("-", " ").split())
    normalized = CASH_TRANSACTION_TYPE_ALIASES.get(compact_value) or CASH_TRANSACTION_TYPE_ALIASES.get(
        value_text
    )
    if normalized is None:
        raise ValidationError(
            "transaction_type is invalid. Allowed values: "
            + ", ".join(ALLOWED_CASH_TRANSACTION_TYPES)
        )
    return normalized


def _normalize_optional_uuid(raw_value: Any, *, field_name: str) -> str | None:
    if raw_value is None:
        return None

    value_text = str(raw_value).strip()
    if not value_text:
        return None

    try:
        return str(UUID(value_text))
    except ValueError as exc:
        raise ValidationError(f'Field "{field_name}" has an invalid value.') from exc


def _truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length]


async def _get_department_row(
    db,
    *,
    organization_id: str,
    department_id: str,
) -> dict[str, Any]:
    row = await db.fetchrow(
        """
        SELECT id, organization_id, is_active
        FROM departments
        WHERE id = $1
        LIMIT 1
        """,
        department_id,
    )
    if row is None:
        raise ValidationError("department_id is invalid")
    if str(row["organization_id"]) != str(organization_id):
        raise ValidationError("department must belong to the same organization")
    return dict(row)


async def _get_expense_category_row(
    db,
    *,
    organization_id: str,
    department_id: str,
    category_id: str,
    field_name: str,
    require_active: bool,
) -> dict[str, Any]:
    repository = ExpenseCategoryRepository(db)
    row = await repository.get_by_id_optional(category_id)
    if row is None:
        raise ValidationError(f'Field "{field_name}" has an invalid value.')
    if str(row.get("organization_id") or "").strip() != str(organization_id):
        raise ValidationError(f'Field "{field_name}" has an invalid value.')
    if str(row.get("department_id") or "").strip() != str(department_id):
        raise ValidationError("expense category must belong to the same department")
    if require_active and row.get("is_active") is False:
        raise ValidationError(f'Field "{field_name}" has an invalid value.')
    return row


async def _count_linked_expenses(
    db,
    *,
    category_id: str,
) -> int:
    row = await db.fetchrow(
        """
        SELECT COUNT(*) AS total
        FROM expenses
        WHERE category_id = $1
        """,
        category_id,
    )
    if row is None:
        return 0
    return int(row["total"] or 0)


class ExpenseCategoryService(BaseService):
    read_schema = ExpenseCategoryReadSchema

    def __init__(self, repository: ExpenseCategoryRepository) -> None:
        super().__init__(repository=repository)

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        organization_id = str(next_data.get("organization_id") or "").strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        department_id = _normalize_optional_uuid(
            next_data.get("department_id"),
            field_name="department_id",
        )
        if department_id is None:
            raise ValidationError("department_id is required")

        await _get_department_row(
            self.repository.db,
            organization_id=organization_id,
            department_id=department_id,
        )
        next_data["department_id"] = department_id
        next_data["is_global"] = False
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        organization_id = str(
            next_data.get("organization_id")
            if next_data.get("organization_id") is not None
            else existing.get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        department_id = _normalize_optional_uuid(
            next_data.get("department_id")
            if "department_id" in next_data
            else existing.get("department_id"),
            field_name="department_id",
        )
        if department_id is None:
            raise ValidationError("department_id is required")

        await _get_department_row(
            self.repository.db,
            organization_id=organization_id,
            department_id=department_id,
        )

        existing_department_id = str(existing.get("department_id") or "").strip()
        if existing_department_id and department_id != existing_department_id:
            linked_expenses = await _count_linked_expenses(
                self.repository.db,
                category_id=str(existing.get("id") or entity_id),
            )
            if linked_expenses > 0:
                raise ValidationError("department_id cannot be changed for a category with expenses")

        next_data["department_id"] = department_id
        next_data["is_global"] = False
        return next_data


class ExpenseService(CreatedByActorMixin, BaseService):
    read_schema = ExpenseReadSchema

    def __init__(self, repository: ExpenseRepository) -> None:
        super().__init__(repository=repository)

    async def _validate_expense_scope(self, payload: dict[str, Any]) -> dict[str, str]:
        organization_id = str(payload.get("organization_id") or "").strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        department_id = _normalize_optional_uuid(
            payload.get("department_id"),
            field_name="department_id",
        )
        if department_id is None:
            raise ValidationError("department_id is required")

        category_id = _normalize_optional_uuid(
            payload.get("category_id"),
            field_name="category_id",
        )
        if category_id is None:
            raise ValidationError("category_id is required")

        await _get_department_row(
            self.repository.db,
            organization_id=organization_id,
            department_id=department_id,
        )
        await _get_expense_category_row(
            self.repository.db,
            organization_id=organization_id,
            department_id=department_id,
            category_id=category_id,
            field_name="category_id",
            require_active=True,
        )

        return {
            "department_id": department_id,
            "category_id": category_id,
        }

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        next_data.update(await self._validate_expense_scope(next_data))
        return next_data

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        normalized_scope = await self._validate_expense_scope({**existing, **next_data})
        if "department_id" in next_data:
            next_data["department_id"] = normalized_scope["department_id"]
        if "category_id" in next_data:
            next_data["category_id"] = normalized_scope["category_id"]
        return next_data

class CashAccountService(BaseService):
    read_schema = CashAccountReadSchema

    def __init__(self, repository: CashAccountRepository) -> None:
        super().__init__(repository=repository)


class CashTransactionService(CreatedByActorMixin, BaseService):
    read_schema = CashTransactionReadSchema

    def __init__(self, repository: CashTransactionRepository) -> None:
        super().__init__(repository=repository)

    @staticmethod
    def _pop_optional_uuid_field(
        payload: dict[str, Any],
        field_name: str,
    ) -> tuple[str | None, bool]:
        if field_name not in payload:
            return None, False

        normalized = _normalize_optional_uuid(payload.pop(field_name), field_name=field_name)
        if normalized is None:
            return None, False

        return normalized, True

    @staticmethod
    def _build_auto_expense_marker(transaction_id: str) -> str:
        return f"{AUTO_EXPENSE_MARKER_PREFIX}{transaction_id}]"

    @classmethod
    def _build_expense_note(
        cls,
        *,
        transaction_id: str,
        transaction_note: Any,
    ) -> str:
        marker = cls._build_auto_expense_marker(transaction_id)
        note_text = str(transaction_note).strip() if transaction_note is not None else ""
        if not note_text:
            return marker
        if marker in note_text:
            return note_text
        return f"{note_text}\n{marker}"

    @classmethod
    def _is_auto_linked_expense(
        cls,
        expense_row: dict[str, Any] | None,
        *,
        transaction_id: str,
    ) -> bool:
        if not expense_row:
            return False
        note_text = str(expense_row.get("note") or "")
        return cls._build_auto_expense_marker(transaction_id) in note_text

    @staticmethod
    def _compose_expense_title(title: Any, *, transaction_id: str) -> str:
        base_title = str(title or "").strip() or "Cash expense"
        suffix = f" [{transaction_id[:8]}]"
        max_base_length = max(1, 255 - len(suffix))
        return _truncate_text(base_title, max_base_length) + suffix

    async def _get_cash_account_for_transaction(
        self,
        *,
        cash_account_id: str,
        organization_id: str,
    ) -> dict[str, Any]:
        account_repository = CashAccountRepository(self.repository.db)
        account = await account_repository.get_by_id_optional(cash_account_id)
        if account is None:
            raise ValidationError("cash_account_id is invalid")

        account_organization_id = str(account.get("organization_id") or "").strip()
        if account_organization_id != organization_id:
            raise ValidationError("cash_account_id is invalid")

        department_id = account.get("department_id")
        if department_id is None:
            raise ValidationError("cash_account_id has no department_id")

        return account

    async def _resolve_expense_category_id(
        self,
        *,
        organization_id: str,
        department_id: str,
        explicit_category_id: str | None,
    ) -> str:
        category_repository = ExpenseCategoryRepository(self.repository.db)
        if explicit_category_id:
            category = await _get_expense_category_row(
                self.repository.db,
                organization_id=organization_id,
                department_id=department_id,
                category_id=explicit_category_id,
                field_name=VIRTUAL_EXPENSE_CATEGORY_FIELD,
                require_active=True,
            )
            return str(category["id"])

        categories = await category_repository.list(
            filters={
                "organization_id": organization_id,
                "department_id": department_id,
                "is_active": True,
            },
            order_by=("name", "code", "id"),
            limit=1,
        )
        if categories:
            return str(categories[0]["id"])

        created_category = await category_repository.create(
            {
                "id": str(uuid4()),
                "organization_id": organization_id,
                "department_id": department_id,
                "name": AUTO_EXPENSE_CATEGORY_NAME,
                "code": f"{AUTO_EXPENSE_CATEGORY_CODE_PREFIX}-{uuid4().hex[:6].upper()}",
                "description": AUTO_EXPENSE_CATEGORY_DESCRIPTION,
                "is_active": True,
                "is_global": False,
            }
        )
        return str(created_category["id"])

    async def _sync_expense_for_transaction(
        self,
        *,
        transaction_payload: dict[str, Any],
        explicit_expense_id: str | None,
        explicit_category_id: str | None,
        actor: CurrentActor | None,
    ) -> str:
        transaction_id = str(transaction_payload.get("id") or "").strip()
        if not transaction_id:
            raise ValidationError("id is required")

        organization_id = str(transaction_payload.get("organization_id") or "").strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        cash_account_id = str(transaction_payload.get("cash_account_id") or "").strip()
        if not cash_account_id:
            raise ValidationError("cash_account_id is required")

        cash_account = await self._get_cash_account_for_transaction(
            cash_account_id=cash_account_id,
            organization_id=organization_id,
        )
        department_id = str(cash_account.get("department_id"))

        expense_repository = ExpenseRepository(self.repository.db)
        linked_expense = None
        if explicit_expense_id:
            linked_expense = await expense_repository.get_by_id_optional(explicit_expense_id)
            if linked_expense is None:
                raise ValidationError('Field "expense_id" has an invalid value.')

            if str(linked_expense.get("organization_id") or "").strip() != organization_id:
                raise ValidationError('Field "expense_id" has an invalid value.')

        if explicit_category_id:
            category_id = await self._resolve_expense_category_id(
                organization_id=organization_id,
                department_id=department_id,
                explicit_category_id=explicit_category_id,
            )
        elif linked_expense is not None and linked_expense.get("category_id") is not None:
            category_id = await self._resolve_expense_category_id(
                organization_id=organization_id,
                department_id=department_id,
                explicit_category_id=str(linked_expense["category_id"]),
            )
        else:
            category_id = await self._resolve_expense_category_id(
                organization_id=organization_id,
                department_id=department_id,
                explicit_category_id=None,
            )

        created_by = _normalize_optional_uuid(
            transaction_payload.get("created_by")
            if transaction_payload.get("created_by") is not None
            else actor.employee_id if actor is not None else None,
            field_name="created_by",
        )

        expense_payload: dict[str, Any] = {
            "organization_id": organization_id,
            "department_id": department_id,
            "category_id": category_id,
            "title": self._compose_expense_title(
                transaction_payload.get("title"),
                transaction_id=transaction_id,
            ),
            # `item` column on expenses is deprecated — form no longer
            # fills it and `title` is the single description field.
            "item": None,
            "amount": transaction_payload.get("amount"),
            "currency": transaction_payload.get("currency"),
            "expense_date": transaction_payload.get("transaction_date"),
            "created_by": created_by,
            "note": self._build_expense_note(
                transaction_id=transaction_id,
                transaction_note=transaction_payload.get("note"),
            ),
        }

        if linked_expense is None:
            created_expense = await expense_repository.create(
                {
                    "id": str(uuid4()),
                    "quantity": None,
                    "unit": None,
                    "unit_price": None,
                    "is_active": True,
                    **expense_payload,
                }
            )
            return str(created_expense["id"])

        update_payload = dict(expense_payload)
        if linked_expense.get("is_active") is False:
            update_payload["is_active"] = True

        updated_expense = await expense_repository.update_by_id(str(linked_expense["id"]), update_payload)
        return str(updated_expense["id"])

    async def _delete_auto_expense_if_detached(
        self,
        *,
        expense_id: str | None,
        transaction_id: str,
    ) -> None:
        if not expense_id:
            return

        expense_repository = ExpenseRepository(self.repository.db)
        linked_expense = await expense_repository.get_by_id_optional(expense_id)
        if linked_expense is None:
            return

        if not self._is_auto_linked_expense(linked_expense, transaction_id=transaction_id):
            return

        linked_rows_total = await self.repository.db.fetchrow(
            """
            SELECT COUNT(*) AS total
            FROM cash_transactions
            WHERE expense_id = $1
              AND id <> $2
            """,
            expense_id,
            transaction_id,
        )
        linked_rows = int(linked_rows_total["total"]) if linked_rows_total is not None else 0
        if linked_rows > 0:
            return

        await expense_repository.delete_by_id(expense_id)

    async def _enrich_transaction_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not rows:
            return rows

        cash_account_ids = {
            str(row["cash_account_id"])
            for row in rows
            if row.get("cash_account_id") is not None
        }
        expense_ids = {
            str(row["expense_id"])
            for row in rows
            if row.get("expense_id") is not None
        }

        cash_account_map: dict[str, dict[str, Any]] = {}
        if cash_account_ids:
            cash_account_rows = await CashAccountRepository(self.repository.db).get_by_ids(
                list(cash_account_ids)
            )
            cash_account_map = {
                str(row["id"]): row
                for row in cash_account_rows
                if row.get("id") is not None
            }

        expense_map: dict[str, dict[str, Any]] = {}
        if expense_ids:
            expense_rows = await ExpenseRepository(self.repository.db).get_by_ids(list(expense_ids))
            expense_map = {
                str(row["id"]): row
                for row in expense_rows
                if row.get("id") is not None
            }

        enriched_rows: list[dict[str, Any]] = []
        for row in rows:
            enriched = dict(row)

            cash_account_id = (
                str(enriched["cash_account_id"]) if enriched.get("cash_account_id") is not None else ""
            )
            if cash_account_id and cash_account_id in cash_account_map:
                department_id = cash_account_map[cash_account_id].get("department_id")
                enriched[VIRTUAL_DEPARTMENT_FIELD] = (
                    str(department_id) if department_id is not None else None
                )
            elif VIRTUAL_DEPARTMENT_FIELD not in enriched:
                enriched[VIRTUAL_DEPARTMENT_FIELD] = None

            expense_id = str(enriched["expense_id"]) if enriched.get("expense_id") is not None else ""
            if expense_id and expense_id in expense_map:
                category_id = expense_map[expense_id].get("category_id")
                enriched[VIRTUAL_EXPENSE_CATEGORY_FIELD] = (
                    str(category_id) if category_id is not None else None
                )
            elif VIRTUAL_EXPENSE_CATEGORY_FIELD not in enriched:
                enriched[VIRTUAL_EXPENSE_CATEGORY_FIELD] = None

            enriched_rows.append(enriched)

        return enriched_rows

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        return [
            *(await super().get_additional_meta_fields(db)),
            {
                "name": "transaction_type",
                "label": "Transaction type",
                "type": "string",
                "database_type": "character varying",
                "nullable": False,
                "required": True,
                "readonly": False,
                "has_default": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "reference": {
                    "table": "__static__",
                    "column": "value",
                    "label_column": "label",
                    "multiple": False,
                    "options": [dict(option) for option in CASH_TRANSACTION_TYPE_OPTIONS],
                },
            },
            {
                "name": VIRTUAL_EXPENSE_CATEGORY_FIELD,
                "label": "Expense category",
                "type": "uuid",
                "database_type": "uuid",
                "nullable": True,
                "required": False,
                "readonly": False,
                "has_default": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "reference": {
                    "table": "expense_categories",
                    "column": "id",
                    "label_column": "name",
                    "multiple": False,
                },
            },
            {
                "name": VIRTUAL_DEPARTMENT_FIELD,
                "label": "Department",
                "type": "uuid",
                "database_type": "uuid",
                "nullable": True,
                "required": False,
                "readonly": True,
                "has_default": False,
                "is_primary_key": False,
                "is_foreign_key": False,
                "reference": {
                    "table": "departments",
                    "column": "id",
                    "label_column": "name",
                    "multiple": False,
                },
            },
        ]

    @staticmethod
    def _normalize_transaction_type_payload(
        payload: dict[str, Any],
        *,
        is_create: bool,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        if "transaction_type" not in next_payload:
            if is_create:
                raise ValidationError("transaction_type is required")
            return next_payload

        next_payload["transaction_type"] = _normalize_cash_transaction_type(
            next_payload.get("transaction_type")
        )
        return next_payload

    def _prepare_create_payload(
        self,
        payload: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_payload = super()._prepare_create_payload(payload, actor=actor)
        return self._normalize_transaction_type_payload(next_payload, is_create=True)

    async def _enforce_leaf_category(self, category_id: str | None) -> None:
        """Raise if the referenced expense_category has children (non-leaf).

        Only leaves may be used in a posted transaction — non-leaf rollups
        are there for reporting, not for bookkeeping.
        """
        if not category_id:
            return
        row = await self.repository.db.fetchrow(
            "SELECT 1 FROM expense_categories WHERE parent_id = $1 LIMIT 1",
            category_id,
        )
        if row is not None:
            raise ValidationError(
                "category_id must reference a leaf category (no child categories)"
            )

    async def _fill_transaction_structured_fields(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> None:
        """Populate F0.6 structured fields on cash_transactions.

        Backs `department_id` from the owning cash_account, snapshots
        `amount_in_base = amount × exchange_rate_to_base`, and mirrors
        the legacy client FK into the polymorphic counterparty pair.
        """
        if not data.get("department_id"):
            cash_account_id = data.get("cash_account_id")
            if cash_account_id:
                organization_id = str(data.get("organization_id") or "").strip()
                if not organization_id and actor is not None:
                    organization_id = actor.organization_id
                account = await self._get_cash_account_for_transaction(
                    cash_account_id=str(cash_account_id),
                    organization_id=organization_id,
                )
                data["department_id"] = str(account["department_id"])

        if not data.get("counterparty_type") and data.get("counterparty_client_id"):
            data["counterparty_type"] = "client"
            data["counterparty_id"] = data.get("counterparty_client_id")

        rate_raw = data.get("exchange_rate_to_base")
        rate = Decimal(str(rate_raw)) if rate_raw is not None else Decimal("1.0")
        amount = Decimal(str(data.get("amount") or 0))
        data["exchange_rate_to_base"] = str(rate)
        data["amount_in_base"] = str((amount * rate).quantize(Decimal("0.01")))

        if not data.get("currency_id") and data.get("currency") and data.get("organization_id"):
            row = await self.repository.db.fetchrow(
                "SELECT id FROM currencies WHERE organization_id = $1 AND code = $2 LIMIT 1",
                data["organization_id"],
                data["currency"],
            )
            if row is not None:
                data["currency_id"] = str(row["id"])

        await self._enforce_leaf_category(data.get("category_id"))

    def _prepare_update_payload(
        self,
        payload: dict[str, Any],
        *,
        actor=None,
    ) -> dict[str, Any]:
        next_payload = super()._prepare_update_payload(payload, actor=actor)
        return self._normalize_transaction_type_payload(next_payload, is_create=False)

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
        items = await self._enrich_transaction_rows(items)
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

    async def get_by_id(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        entity = await self.repository.get_by_id(entity_id)
        self._ensure_actor_can_access_entity(entity, actor=actor)
        enriched = await self._enrich_transaction_rows([entity])
        return Result.ok_result(self._map_read(enriched[0]))

    async def create(self, payload: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        explicit_category_id, _ = self._pop_optional_uuid_field(data, VIRTUAL_EXPENSE_CATEGORY_FIELD)
        data.pop(VIRTUAL_DEPARTMENT_FIELD, None)

        data = self._prepare_create_payload(data, actor=actor)
        data = self._apply_actor_organization_on_create(data, actor=actor)
        data = await self._validate_catalog_fields(data, actor=actor, existing=None, is_create=True)

        async with self.repository.db.transaction():
            transaction_type = str(data.get("transaction_type") or "").strip().lower()
            explicit_expense_id = _normalize_optional_uuid(data.get("expense_id"), field_name="expense_id")
            if transaction_type == "expense":
                data["expense_id"] = await self._sync_expense_for_transaction(
                    transaction_payload=data,
                    explicit_expense_id=explicit_expense_id,
                    explicit_category_id=explicit_category_id,
                    actor=actor,
                )
            else:
                data["expense_id"] = None

            await self._fill_transaction_structured_fields(data, actor=actor)

            entity = await self.repository.create(data)
            enriched_entity = (await self._enrich_transaction_rows([entity]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity.get(self.repository.id_column),
                entity=enriched_entity,
                actor=actor,
            )
            await self._record_audit_event(
                action="create",
                entity_id=entity.get(self.repository.id_column),
                before_data=None,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched_entity))

    async def update(
        self,
        entity_id: Any,
        payload: Any,
        *,
        actor: CurrentActor | None = None,
    ) -> Result[Any]:
        data = self._payload_to_dict(payload)
        explicit_category_id, _ = self._pop_optional_uuid_field(data, VIRTUAL_EXPENSE_CATEGORY_FIELD)
        data.pop(VIRTUAL_DEPARTMENT_FIELD, None)

        data = self._prepare_update_payload(data, actor=actor)

        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            enriched_existing = (await self._enrich_transaction_rows([existing]))[0]
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=enriched_existing,
                actor=actor,
            )

            data = self._apply_actor_organization_on_update(data, actor=actor)
            data = await self._validate_catalog_fields(
                data,
                actor=actor,
                existing=existing,
                is_create=False,
            )

            merged_payload = {**existing, **data}
            merged_payload["id"] = str(existing.get("id") or entity_id)
            transaction_type = str(merged_payload.get("transaction_type") or "").strip().lower()
            existing_expense_id = _normalize_optional_uuid(
                existing.get("expense_id"),
                field_name="expense_id",
            )
            explicit_expense_id = _normalize_optional_uuid(
                data.get("expense_id") if "expense_id" in data else existing.get("expense_id"),
                field_name="expense_id",
            )

            if transaction_type == "expense":
                data["expense_id"] = await self._sync_expense_for_transaction(
                    transaction_payload=merged_payload,
                    explicit_expense_id=explicit_expense_id,
                    explicit_category_id=explicit_category_id,
                    actor=actor,
                )
            else:
                data["expense_id"] = None
                await self._delete_auto_expense_if_detached(
                    expense_id=existing_expense_id,
                    transaction_id=str(existing.get("id") or entity_id),
                )

            entity = await self.repository.update_by_id(entity_id, data)
            enriched_entity = (await self._enrich_transaction_rows([entity]))[0]
            after_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=enriched_entity,
                actor=actor,
            )
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(enriched_entity))

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[bool]:
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            enriched_existing = (await self._enrich_transaction_rows([existing]))[0]
            before_snapshot = await self._capture_audit_snapshot(
                entity_id,
                entity=enriched_existing,
                actor=actor,
            )

            existing_expense_id = _normalize_optional_uuid(
                existing.get("expense_id"),
                field_name="expense_id",
            )
            await self._delete_auto_expense_if_detached(
                expense_id=existing_expense_id,
                transaction_id=str(existing.get("id") or entity_id),
            )

            deleted = await self.repository.delete_by_id(entity_id)
            if deleted:
                await self._record_audit_event(
                    action="delete",
                    entity_id=entity_id,
                    before_data=before_snapshot,
                    after_data=None,
                    actor=actor,
                )
        return Result.ok_result(deleted)


def _normalize_decimal(raw_value: Any, *, field_name: str) -> Decimal:
    try:
        return Decimal(str(raw_value))
    except Exception as exc:
        raise ValidationError(f"{field_name} has an invalid value") from exc


def _normalize_debt_date(raw_value: Any, *, field_name: str) -> date | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, datetime):
        return raw_value.date()
    if isinstance(raw_value, date):
        return raw_value
    if not isinstance(raw_value, str):
        raise ValidationError(f"{field_name} has an invalid value")
    text = raw_value.strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ValidationError(f"{field_name} has an invalid value") from exc


def _resolve_debt_status(
    amount_total: Decimal,
    amount_paid: Decimal,
    requested_status: Any,
) -> str:
    normalized = str(requested_status or "").strip().lower()
    if normalized == "cancelled":
        return "cancelled"
    if amount_paid <= Decimal("0"):
        return "open"
    if amount_paid >= amount_total:
        return "closed"
    return "partially_paid"


class SupplierDebtService(BaseService):
    read_schema = SupplierDebtReadSchema

    def __init__(self, repository: SupplierDebtRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                {
                    "name": "item_type",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(sorted(ITEM_TYPES)),
                    },
                },
                {
                    "name": "status",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(list(DEBT_STATUSES)),
                    },
                },
                {
                    "name": "item_key",
                    "reference": {
                        "table": ITEM_KEY_REFERENCE_TABLE,
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": [],
                    },
                },
            ]
        )
        return fields

    async def get_reference_options(
        self,
        field_name: str,
        *,
        db,
        actor: CurrentActor | None = None,
        search: str | None = None,
        values=None,
        limit: int = 25,
        extra_params=None,
    ) -> list[dict[str, str]] | None:
        if field_name != "item_key":
            return None

        normalized_item_type = str((extra_params or {}).get("item_type") or "").strip().lower()
        if normalized_item_type not in ITEM_TYPES:
            return []

        normalized_department_id = str((extra_params or {}).get("department_id") or "").strip() or None
        organization_id = str(
            (actor.organization_id if actor is not None else None)
            or (extra_params or {}).get("organization_id")
            or ""
        ).strip()
        if not organization_id:
            return []

        normalized_values = [str(value).strip() for value in (values or []) if str(value).strip()]
        return await _fetch_inventory_item_key_options(
            db=db,
            organization_id=organization_id,
            item_type=normalized_item_type,
            department_id=normalized_department_id,
            search=search,
            values=normalized_values,
            limit=limit,
        )

    async def _prepare_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None,
        existing: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(payload)
        existing_item_type = existing.get("item_type") if existing is not None else None
        existing_item_key = existing.get("item_key") if existing is not None else None
        existing_unit = existing.get("unit") if existing is not None else None
        item_type = str(next_payload.get("item_type") or existing_item_type or "").strip().lower()
        item_key = str(next_payload.get("item_key") or existing_item_key or "").strip()
        unit = normalize_stock_movement_unit(next_payload.get("unit") or existing_unit)
        department_id = str(
            next_payload.get("department_id")
            or (existing.get("department_id") if existing else None)
            or ""
        ).strip()
        organization_id = str(
            next_payload.get("organization_id")
            or (existing.get("organization_id") if existing else None)
            or (actor.organization_id if actor is not None else "")
            or ""
        ).strip()
        amount_total = _normalize_decimal(
            next_payload.get("amount_total")
            if "amount_total" in next_payload
            else existing.get("amount_total") if existing else None,
            field_name="amount_total",
        )
        amount_paid = _normalize_decimal(
            next_payload.get("amount_paid")
            if "amount_paid" in next_payload
            else existing.get("amount_paid") if existing else Decimal("0"),
            field_name="amount_paid",
        )
        quantity = _normalize_decimal(
            next_payload.get("quantity")
            if "quantity" in next_payload
            else existing.get("quantity") if existing else None,
            field_name="quantity",
        )

        if item_type not in ITEM_TYPES:
            raise ValidationError("item_type is invalid")
        if not item_key:
            raise ValidationError("item_key is required")
        if not department_id:
            raise ValidationError("department_id is required")
        if not organization_id:
            raise ValidationError("organization_id is required")
        if amount_total < Decimal("0"):
            raise ValidationError("amount_total must be non-negative")
        if amount_paid < Decimal("0"):
            raise ValidationError("amount_paid must be non-negative")
        if amount_paid > amount_total:
            raise ValidationError("amount_paid cannot exceed amount_total")
        if quantity <= Decimal("0"):
            raise ValidationError("quantity must be positive")

        issued_on = _normalize_debt_date(
            next_payload.get("issued_on")
            if "issued_on" in next_payload
            else existing.get("issued_on") if existing else None,
            field_name="issued_on",
        )
        due_on = _normalize_debt_date(
            next_payload.get("due_on")
            if "due_on" in next_payload
            else existing.get("due_on") if existing else None,
            field_name="due_on",
        )
        if issued_on is not None and due_on is not None and due_on < issued_on:
            raise ValidationError("due_on cannot be before issued_on")

        client_id = _normalize_optional_uuid(
            next_payload.get("client_id")
            if "client_id" in next_payload
            else existing.get("client_id") if existing else None,
            field_name="client_id",
        )
        if client_id is None:
            raise ValidationError("client_id is required")

        supplier_row = await ClientRepository(self.repository.db).get_by_id_optional(client_id)
        if supplier_row is None or str(supplier_row.get("organization_id") or "").strip() != organization_id:
            raise ValidationError("client_id is invalid")

        if not await _inventory_item_key_exists(
            db=self.repository.db,
            organization_id=organization_id,
            item_type=item_type,
            item_key=item_key,
            department_id=department_id,
        ):
            raise ValidationError("item_key is invalid for selected item_type")

        next_payload["item_type"] = item_type
        next_payload["item_key"] = item_key
        next_payload["unit"] = unit
        next_payload["department_id"] = department_id
        next_payload["organization_id"] = organization_id
        next_payload["client_id"] = client_id
        next_payload["amount_total"] = str(amount_total)
        next_payload["amount_paid"] = str(amount_paid)
        next_payload["quantity"] = str(quantity)
        next_payload["status"] = _resolve_debt_status(
            amount_total=amount_total,
            amount_paid=amount_paid,
            requested_status=next_payload.get("status")
            if "status" in next_payload
            else existing.get("status") if existing else None,
        )
        return next_payload

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        return await self._prepare_payload(data, actor=actor, existing=None)

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_payload = dict(data)
        if "organization_id" in next_payload and str(next_payload["organization_id"]) != str(existing["organization_id"]):
            raise ValidationError("organization_id is immutable")
        if "department_id" in next_payload and str(next_payload["department_id"]) != str(existing["department_id"]):
            raise ValidationError("department_id is immutable")
        if "client_id" in next_payload and str(next_payload["client_id"]) != str(existing["client_id"]):
            raise ValidationError("client_id is immutable")
        return await self._prepare_payload(next_payload, actor=actor, existing=existing)


class DebtPaymentService(CreatedByActorMixin, BaseService):
    """Payment record against a client or supplier debt.

    Maintains four invariants on every create/update/delete:
      1. Exactly one of ``client_debt_id`` / ``supplier_debt_id`` is set.
      2. ``direction`` matches parent (incoming → client, outgoing → supplier).
      3. The parent debt's ``amount_paid`` equals SUM(active payments) and
         ``status`` is recomputed accordingly.
      4. If ``cash_account_id`` is set, a matching ``CashTransaction`` is
         created (and kept in sync on update/delete) so the ledger balances.
    """

    read_schema = DebtPaymentReadSchema

    def __init__(self, repository: DebtPaymentRepository) -> None:
        super().__init__(repository=repository)

    async def get_additional_meta_fields(self, db) -> list[dict[str, Any]]:
        fields = await super().get_additional_meta_fields(db)
        fields.extend(
            [
                {
                    "name": "direction",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(list(DEBT_PAYMENT_DIRECTIONS)),
                    },
                },
                {
                    "name": "method",
                    "reference": {
                        "table": "__static__",
                        "column": "value",
                        "label_column": "label",
                        "multiple": False,
                        "options": self._build_static_reference_options(list(DEBT_PAYMENT_METHODS)),
                    },
                },
            ]
        )
        return fields

    @staticmethod
    def _build_marker(payment_id: str) -> str:
        return f"{DEBT_PAYMENT_MARKER_PREFIX}{payment_id}]"

    @classmethod
    def _compose_note(cls, *, payment_id: str, source_note: Any) -> str:
        marker = cls._build_marker(payment_id)
        note_text = str(source_note).strip() if source_note is not None else ""
        if not note_text:
            return marker
        if marker in note_text:
            return note_text
        return f"{note_text}\n{marker}"

    @staticmethod
    def _compose_title(
        *,
        direction: str,
        debt_row: dict[str, Any],
        supplier_name: str | None = None,
        client_name: str | None = None,
    ) -> str:
        item_key = str(debt_row.get("item_key") or "").strip()
        item_type = str(debt_row.get("item_type") or "").strip()
        counterparty = supplier_name or client_name or ""
        if direction == "incoming":
            base = f"Debt payment from {counterparty}".strip()
        else:
            base = f"Debt payment to {counterparty}".strip()
        tag = " · ".join([part for part in (item_type, item_key) if part])
        full = f"{base} ({tag})" if tag else base
        if len(full) > AUTO_DEBT_CASH_TITLE_MAX_LEN:
            full = full[:AUTO_DEBT_CASH_TITLE_MAX_LEN]
        return full or "Debt payment"

    async def _load_parent(
        self,
        *,
        client_debt_id: str | None,
        supplier_debt_id: str | None,
    ) -> tuple[str, dict[str, Any]]:
        if bool(client_debt_id) == bool(supplier_debt_id):
            raise ValidationError(
                "Exactly one of client_debt_id or supplier_debt_id must be set"
            )
        if client_debt_id:
            row = await ClientDebtRepository(self.repository.db).get_by_id_optional(client_debt_id)
            if row is None:
                raise ValidationError("client_debt_id is invalid")
            return "incoming", row
        row = await SupplierDebtRepository(self.repository.db).get_by_id_optional(supplier_debt_id)
        if row is None:
            raise ValidationError("supplier_debt_id is invalid")
        return "outgoing", row

    async def _recalculate_parent(
        self,
        *,
        direction: str,
        debt_row: dict[str, Any],
    ) -> None:
        debt_id = str(debt_row["id"])
        column = "client_debt_id" if direction == "incoming" else "supplier_debt_id"
        row = await self.repository.db.fetchrow(
            f"""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM debt_payments
            WHERE {column} = $1 AND is_active = TRUE
            """,
            debt_id,
        )
        total_paid = Decimal(str(row["total"])) if row is not None else Decimal("0")
        amount_total = Decimal(str(debt_row.get("amount_total") or 0))
        if total_paid > amount_total:
            raise ValidationError("Total payments exceed the debt amount_total")

        new_status = _resolve_debt_status(
            amount_total=amount_total,
            amount_paid=total_paid,
            requested_status=debt_row.get("status"),
        )
        table = "client_debts" if direction == "incoming" else "supplier_debts"
        await self.repository.db.execute(
            f"UPDATE {table} SET amount_paid = $1, status = $2, updated_at = NOW() WHERE id = $3",
            str(total_paid),
            new_status,
            debt_id,
        )

    async def _sync_cash_transaction(
        self,
        *,
        payment_row: dict[str, Any],
        debt_row: dict[str, Any],
        direction: str,
        actor: CurrentActor | None,
    ) -> str | None:
        cash_account_id = str(payment_row.get("cash_account_id") or "").strip()
        if not cash_account_id:
            return None

        organization_id = str(debt_row.get("organization_id") or "").strip()
        if not organization_id:
            raise ValidationError("organization_id is required")

        account_repo = CashAccountRepository(self.repository.db)
        account = await account_repo.get_by_id_optional(cash_account_id)
        if account is None:
            raise ValidationError("cash_account_id is invalid")
        if str(account.get("organization_id") or "").strip() != organization_id:
            raise ValidationError("cash_account_id is invalid")

        payment_id = str(payment_row["id"])
        transaction_type = "income" if direction == "incoming" else "expense"
        counterparty_client_id = str(debt_row.get("client_id") or "")

        tx_payload: dict[str, Any] = {
            "organization_id": organization_id,
            "cash_account_id": cash_account_id,
            "expense_id": None,
            "counterparty_client_id": counterparty_client_id or None,
            "created_by": actor.employee_id if actor is not None else None,
            "title": self._compose_title(
                direction=direction,
                debt_row=debt_row,
            ),
            "transaction_type": transaction_type,
            "amount": str(payment_row.get("amount")),
            "currency": str(payment_row.get("currency") or debt_row.get("currency") or ""),
            "transaction_date": payment_row.get("paid_on"),
            "reference_no": payment_row.get("reference_no"),
            "note": self._compose_note(
                payment_id=payment_id,
                source_note=payment_row.get("note"),
            ),
            "is_active": True,
        }

        tx_repo = CashTransactionRepository(self.repository.db)
        existing_tx_id = str(payment_row.get("cash_transaction_id") or "").strip()
        if existing_tx_id:
            existing_tx = await tx_repo.get_by_id_optional(existing_tx_id)
            if existing_tx is not None:
                await tx_repo.update_by_id(existing_tx_id, tx_payload)
                return existing_tx_id

        created = await tx_repo.create({"id": str(uuid4()), **tx_payload})
        return str(created["id"])

    async def _delete_linked_cash_transaction(
        self,
        *,
        cash_transaction_id: str | None,
        payment_id: str,
    ) -> None:
        if not cash_transaction_id:
            return
        tx_repo = CashTransactionRepository(self.repository.db)
        tx_row = await tx_repo.get_by_id_optional(cash_transaction_id)
        if tx_row is None:
            return
        marker = self._build_marker(payment_id)
        if marker not in str(tx_row.get("note") or ""):
            return
        await tx_repo.delete_by_id(cash_transaction_id)

    async def _prepare_payload(
        self,
        payload: dict[str, Any],
        *,
        actor: CurrentActor | None,
        existing: dict[str, Any] | None,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        next_payload = dict(payload)

        client_debt_id = _normalize_optional_uuid(
            next_payload.get("client_debt_id")
            if "client_debt_id" in next_payload
            else (existing.get("client_debt_id") if existing else None),
            field_name="client_debt_id",
        )
        supplier_debt_id = _normalize_optional_uuid(
            next_payload.get("supplier_debt_id")
            if "supplier_debt_id" in next_payload
            else (existing.get("supplier_debt_id") if existing else None),
            field_name="supplier_debt_id",
        )
        direction, debt_row = await self._load_parent(
            client_debt_id=client_debt_id,
            supplier_debt_id=supplier_debt_id,
        )

        if existing is not None:
            existing_direction = "incoming" if existing.get("client_debt_id") else "outgoing"
            if existing_direction != direction:
                raise ValidationError("direction is immutable")

        requested_direction = str(next_payload.get("direction") or direction).strip().lower()
        if requested_direction not in DEBT_PAYMENT_DIRECTIONS:
            raise ValidationError("direction is invalid")
        if requested_direction != direction:
            raise ValidationError("direction must match the parent debt")

        method = str(next_payload.get("method") or (existing.get("method") if existing else "cash")).strip().lower()
        if method not in DEBT_PAYMENT_METHODS:
            raise ValidationError("method is invalid")

        amount = _normalize_decimal(
            next_payload.get("amount")
            if "amount" in next_payload
            else (existing.get("amount") if existing else None),
            field_name="amount",
        )
        if amount <= Decimal("0"):
            raise ValidationError("amount must be positive")

        paid_on = _normalize_debt_date(
            next_payload.get("paid_on")
            if "paid_on" in next_payload
            else (existing.get("paid_on") if existing else None),
            field_name="paid_on",
        )
        if paid_on is None:
            raise ValidationError("paid_on is required")

        currency = str(
            next_payload.get("currency")
            or (existing.get("currency") if existing else None)
            or debt_row.get("currency")
            or ""
        ).strip()
        if not currency:
            raise ValidationError("currency is required")
        if currency != str(debt_row.get("currency") or "").strip():
            raise ValidationError("currency must match the parent debt currency")

        cash_account_id = _normalize_optional_uuid(
            next_payload.get("cash_account_id")
            if "cash_account_id" in next_payload
            else (existing.get("cash_account_id") if existing else None),
            field_name="cash_account_id",
        )

        organization_id = str(debt_row.get("organization_id") or "").strip()
        department_id = str(debt_row.get("department_id") or "").strip()

        # cap amount at remaining balance taking into account this payment's
        # own prior amount if updating (so editing upward to the new cap works)
        total_active = await self.repository.db.fetchrow(
            f"""
            SELECT COALESCE(SUM(amount), 0) AS total
            FROM debt_payments
            WHERE {'client_debt_id' if direction == 'incoming' else 'supplier_debt_id'} = $1
              AND is_active = TRUE
              AND ($2::uuid IS NULL OR id <> $2::uuid)
            """,
            str(debt_row["id"]),
            str(existing["id"]) if existing is not None else None,
        )
        other_total = Decimal(str(total_active["total"])) if total_active is not None else Decimal("0")
        debt_total = Decimal(str(debt_row.get("amount_total") or 0))
        if other_total + amount > debt_total:
            raise ValidationError("Payment would exceed debt amount_total")

        next_payload["organization_id"] = organization_id
        next_payload["department_id"] = department_id
        next_payload["client_debt_id"] = client_debt_id
        next_payload["supplier_debt_id"] = supplier_debt_id
        next_payload["direction"] = direction
        next_payload["method"] = method
        next_payload["amount"] = str(amount)
        next_payload["currency"] = currency
        next_payload["paid_on"] = paid_on
        next_payload["cash_account_id"] = cash_account_id
        next_payload["is_active"] = next_payload.get("is_active", existing.get("is_active") if existing else True)

        return next_payload, direction, debt_row

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        prepared, _direction, _debt_row = await self._prepare_payload(
            data, actor=actor, existing=None,
        )
        return prepared

    async def _before_update(
        self,
        entity_id: Any,
        data: dict[str, Any],
        *,
        existing: dict[str, Any],
        actor: CurrentActor | None = None,
    ) -> dict[str, Any]:
        next_data = dict(data)
        if "client_debt_id" in next_data and str(next_data["client_debt_id"] or "") != str(existing.get("client_debt_id") or ""):
            raise ValidationError("client_debt_id is immutable")
        if "supplier_debt_id" in next_data and str(next_data["supplier_debt_id"] or "") != str(existing.get("supplier_debt_id") or ""):
            raise ValidationError("supplier_debt_id is immutable")
        prepared, _direction, _debt_row = await self._prepare_payload(
            next_data, actor=actor, existing=existing,
        )
        return prepared

    async def create(self, payload: Any, *, actor: CurrentActor | None = None) -> Result[Any]:
        data = self._payload_to_dict(payload)
        data = self._prepare_create_payload(data, actor=actor)
        data = self._apply_actor_organization_on_create(data, actor=actor)

        async with self.repository.db.transaction():
            prepared, direction, debt_row = await self._prepare_payload(
                data, actor=actor, existing=None,
            )
            payment_id = str(uuid4())
            prepared["id"] = payment_id
            # reserve the cash_transaction_id column; may be filled below
            prepared.setdefault("cash_transaction_id", None)

            entity = await self.repository.create(prepared)

            tx_id = await self._sync_cash_transaction(
                payment_row=entity,
                debt_row=debt_row,
                direction=direction,
                actor=actor,
            )
            if tx_id:
                entity = await self.repository.update_by_id(
                    entity["id"], {"cash_transaction_id": tx_id},
                )

            await self._recalculate_parent(direction=direction, debt_row=debt_row)

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
        return Result.ok_result(self._map_read(entity))

    async def update(
        self,
        entity_id: Any,
        payload: Any,
        *,
        actor: CurrentActor | None = None,
    ) -> Result[Any]:
        data = self._payload_to_dict(payload)
        data = self._prepare_update_payload(data, actor=actor)

        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id, entity=existing, actor=actor,
            )

            data = self._apply_actor_organization_on_update(data, actor=actor)
            prepared, direction, debt_row = await self._prepare_payload(
                data, actor=actor, existing=existing,
            )
            entity = await self.repository.update_by_id(entity_id, prepared)

            tx_id = await self._sync_cash_transaction(
                payment_row=entity,
                debt_row=debt_row,
                direction=direction,
                actor=actor,
            )
            if tx_id and tx_id != str(entity.get("cash_transaction_id") or ""):
                entity = await self.repository.update_by_id(
                    entity_id, {"cash_transaction_id": tx_id},
                )

            await self._recalculate_parent(direction=direction, debt_row=debt_row)

            after_snapshot = await self._capture_audit_snapshot(
                entity_id, entity=entity, actor=actor,
            )
            await self._record_audit_event(
                action="update",
                entity_id=entity_id,
                before_data=before_snapshot,
                after_data=after_snapshot,
                actor=actor,
            )
        return Result.ok_result(self._map_read(entity))

    async def delete(self, entity_id: Any, *, actor: CurrentActor | None = None) -> Result[bool]:
        async with self.repository.db.transaction():
            existing = await self.repository.get_by_id(entity_id)
            self._ensure_actor_can_access_entity(existing, actor=actor)
            before_snapshot = await self._capture_audit_snapshot(
                entity_id, entity=existing, actor=actor,
            )

            direction = "incoming" if existing.get("client_debt_id") else "outgoing"
            if direction == "incoming":
                debt_row = await ClientDebtRepository(self.repository.db).get_by_id_optional(
                    existing["client_debt_id"],
                )
            else:
                debt_row = await SupplierDebtRepository(self.repository.db).get_by_id_optional(
                    existing["supplier_debt_id"],
                )

            await self._delete_linked_cash_transaction(
                cash_transaction_id=str(existing.get("cash_transaction_id") or "") or None,
                payment_id=str(existing["id"]),
            )

            deleted = await self.repository.delete_by_id(entity_id)
            if deleted and debt_row is not None:
                await self._recalculate_parent(direction=direction, debt_row=debt_row)

            if deleted:
                await self._record_audit_event(
                    action="delete",
                    entity_id=entity_id,
                    before_data=before_snapshot,
                    after_data=None,
                    actor=actor,
                )
        return Result.ok_result(deleted)


class EmployeeAdvanceService(CreatedByActorMixin, BaseService):
    """Подотчётные — cash handed out to an employee, reconciled by receipts.

    Balance is derived from cash_transactions via source_type/source_id:
    - 'advance': issuance (initial outflow)
    - 'advance_reconciliation': receipts submitted (becomes expense)
    - 'advance_return': leftover back to cash
    outstanding = issued − reconciled − returned.
    """

    read_schema = EmployeeAdvanceReadSchema

    def __init__(self, repository: EmployeeAdvanceRepository) -> None:
        super().__init__(repository=repository)

    async def compute_balance(self, advance_id: str) -> dict[str, Decimal]:
        advance = await self.repository.get_by_id(advance_id)
        totals_row = await self.repository.db.fetchrow(
            """
            SELECT
                COALESCE(SUM(CASE WHEN source_type = 'advance_reconciliation' THEN amount ELSE 0 END), 0) AS reconciled,
                COALESCE(SUM(CASE WHEN source_type = 'advance_return' THEN amount ELSE 0 END), 0) AS returned
            FROM cash_transactions
            WHERE source_id = $1
            """,
            advance_id,
        )
        issued = Decimal(str(advance.get("amount_issued") or 0))
        reconciled = Decimal(str((totals_row or {}).get("reconciled") or 0))
        returned = Decimal(str((totals_row or {}).get("returned") or 0))
        outstanding = (issued - reconciled - returned).quantize(Decimal("0.01"))
        return {
            "advance_id": advance_id,
            "amount_issued": issued,
            "amount_reconciled": reconciled,
            "amount_returned": returned,
            "amount_outstanding": outstanding,
            "currency": advance.get("currency"),
            "status": advance.get("status"),
        }


__all__ = [
    "ExpenseCategoryService",
    "ExpenseService",
    "CashAccountService",
    "CashTransactionService",
    "SupplierDebtService",
    "DebtPaymentService",
    "EmployeeAdvanceService",
]
