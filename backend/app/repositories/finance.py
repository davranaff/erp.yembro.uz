from __future__ import annotations

from app.repositories.base import BaseRepository


class ExpenseCategoryRepository(BaseRepository[dict[str, object]]):
    table = "expense_categories"


class CashAccountRepository(BaseRepository[dict[str, object]]):
    table = "cash_accounts"


class CashTransactionRepository(BaseRepository[dict[str, object]]):
    table = "cash_transactions"


class SupplierDebtRepository(BaseRepository[dict[str, object]]):
    table = "supplier_debts"


class DebtPaymentRepository(BaseRepository[dict[str, object]]):
    table = "debt_payments"


class EmployeeAdvanceRepository(BaseRepository[dict[str, object]]):
    table = "employee_advances"


__all__ = [
    "ExpenseCategoryRepository",
    "CashAccountRepository",
    "CashTransactionRepository",
    "SupplierDebtRepository",
    "DebtPaymentRepository",
    "EmployeeAdvanceRepository",
]
