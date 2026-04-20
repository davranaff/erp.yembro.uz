from __future__ import annotations

from datetime import date as date_type
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.api.crud import build_crud_router
from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.db.pool import Database
from app.repositories.finance import (
    CashAccountRepository,
    CashTransactionRepository,
    DebtPaymentRepository,
    ExpenseCategoryRepository,
    ExpenseRepository,
    SupplierDebtRepository,
)
from app.services.finance import (
    CashAccountService,
    CashTransactionService,
    DebtPaymentService,
    ExpenseCategoryService,
    ExpenseService,
    SupplierDebtService,
)


router = APIRouter(prefix="/finance", tags=["finance"])


_AGING_BUCKETS_SQL = """
SELECT
    COALESCE(SUM(CASE WHEN days_overdue IS NULL OR days_overdue <= 0 THEN outstanding ELSE 0 END), 0) AS not_due,
    COALESCE(SUM(CASE WHEN days_overdue BETWEEN 1 AND 30 THEN outstanding ELSE 0 END), 0) AS bucket_0_30,
    COALESCE(SUM(CASE WHEN days_overdue BETWEEN 31 AND 60 THEN outstanding ELSE 0 END), 0) AS bucket_31_60,
    COALESCE(SUM(CASE WHEN days_overdue BETWEEN 61 AND 90 THEN outstanding ELSE 0 END), 0) AS bucket_61_90,
    COALESCE(SUM(CASE WHEN days_overdue > 90 THEN outstanding ELSE 0 END), 0) AS bucket_90_plus,
    COALESCE(SUM(outstanding), 0) AS total
FROM (
    SELECT
        (amount_total - amount_paid) AS outstanding,
        CASE WHEN due_on IS NULL THEN NULL ELSE ($2::date - due_on) END AS days_overdue
    FROM {table}
    WHERE organization_id = $1
      AND status IN ('open', 'partially_paid')
      AND is_active = TRUE
      AND (amount_total - amount_paid) > 0
      AND ($3::uuid[] IS NULL OR department_id = ANY($3::uuid[]))
) AS sub
"""


def _aging_sql(table: str) -> str:
    return _AGING_BUCKETS_SQL.format(table=table)


def _row_to_buckets(row: Any | None) -> dict[str, Any]:
    row = row or {}
    return {
        "not_due": float(row.get("not_due") or 0),
        "bucket_0_30": float(row.get("bucket_0_30") or 0),
        "bucket_31_60": float(row.get("bucket_31_60") or 0),
        "bucket_61_90": float(row.get("bucket_61_90") or 0),
        "bucket_90_plus": float(row.get("bucket_90_plus") or 0),
        "total": float(row.get("total") or 0),
    }


@router.get(
    "/debts/aging",
    dependencies=[Depends(require_access("supplier_debt.read"))],
)
async def get_debts_aging(
    as_of: date_type | None = Query(default=None),
    department_id: list[str] | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> dict[str, Any]:
    effective_as_of = as_of or date_type.today()
    normalized_department_ids = [
        value.strip() for value in (department_id or []) if value and value.strip()
    ]
    department_id_param = normalized_department_ids or None
    receivables_row = await db.fetchrow(
        _aging_sql("client_debts"),
        current_actor.organization_id,
        effective_as_of,
        department_id_param,
    )
    payables_row = await db.fetchrow(
        _aging_sql("supplier_debts"),
        current_actor.organization_id,
        effective_as_of,
        department_id_param,
    )
    return {
        "as_of": effective_as_of.isoformat(),
        "receivables": _row_to_buckets(receivables_row),
        "payables": _row_to_buckets(payables_row),
    }

router.include_router(
    build_crud_router(
        prefix="expense-categories",
        service_factory=lambda db: ExpenseCategoryService(ExpenseCategoryRepository(db)),
        permission_prefix="expense_category",
        tags=["expense-category"],
    )
)

router.include_router(
    build_crud_router(
        prefix="expenses",
        service_factory=lambda db: ExpenseService(ExpenseRepository(db)),
        permission_prefix="expense",
        tags=["expense"],
    )
)

router.include_router(
    build_crud_router(
        prefix="cash-accounts",
        service_factory=lambda db: CashAccountService(CashAccountRepository(db)),
        permission_prefix="cash_account",
        tags=["cash-account"],
    )
)

router.include_router(
    build_crud_router(
        prefix="cash-transactions",
        service_factory=lambda db: CashTransactionService(CashTransactionRepository(db)),
        permission_prefix="cash_transaction",
        tags=["cash-transaction"],
    )
)

router.include_router(
    build_crud_router(
        prefix="supplier-debts",
        service_factory=lambda db: SupplierDebtService(SupplierDebtRepository(db)),
        permission_prefix="supplier_debt",
        tags=["supplier-debt"],
    )
)

router.include_router(
    build_crud_router(
        prefix="debt-payments",
        service_factory=lambda db: DebtPaymentService(DebtPaymentRepository(db)),
        permission_prefix="debt_payment",
        tags=["debt-payment"],
    )
)

register_module_stats_route(
    router,
    module="finance",
    label="Finance",
    tables=(
        ModuleStatsTable(key="expense_categories", label="Expense Categories", table="expense_categories"),
        ModuleStatsTable(key="expenses", label="Expenses", table="expenses"),
        ModuleStatsTable(key="cash_accounts", label="Cash Accounts", table="cash_accounts"),
        ModuleStatsTable(key="cash_transactions", label="Cash Transactions", table="cash_transactions"),
        ModuleStatsTable(key="supplier_debts", label="Supplier Debts", table="supplier_debts"),
        ModuleStatsTable(key="debt_payments", label="Debt Payments", table="debt_payments"),
    ),
)

__all__ = ["router"]
