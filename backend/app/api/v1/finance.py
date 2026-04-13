from __future__ import annotations

from fastapi import APIRouter

from app.api.crud import build_crud_router
from app.api.module_stats import ModuleStatsTable, register_module_stats_route
from app.repositories.finance import (
    CashAccountRepository,
    CashTransactionRepository,
    ExpenseCategoryRepository,
    ExpenseRepository,
)
from app.services.finance import (
    CashAccountService,
    CashTransactionService,
    ExpenseCategoryService,
    ExpenseService,
)


router = APIRouter(prefix="/finance", tags=["finance"])

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

register_module_stats_route(
    router,
    module="finance",
    label="Finance",
    tables=(
        ModuleStatsTable(key="expense_categories", label="Expense Categories", table="expense_categories"),
        ModuleStatsTable(key="expenses", label="Expenses", table="expenses"),
        ModuleStatsTable(key="cash_accounts", label="Cash Accounts", table="cash_accounts"),
        ModuleStatsTable(key="cash_transactions", label="Cash Transactions", table="cash_transactions"),
    ),
)

__all__ = ["router"]
