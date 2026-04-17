from __future__ import annotations

from app.schemas.base import (
    BaseCreateSchema,
    BaseReadSchema,
    BaseUpdateSchema,
    CRUDBaseParams,
    CRUDListResponse,
    OpenSchema,
)


class ExpenseCategoryCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create expense category."""


class ExpenseCategoryUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update expense category."""


class ExpenseCategoryReadSchema(OpenSchema, BaseReadSchema):
    """Readable expense category response."""


class ExpenseCategoryListParams(CRUDBaseParams):
    """Pagination + query params for expense category list."""


class ExpenseCategoryListResponse(CRUDListResponse[ExpenseCategoryReadSchema]):
    """Paginated expense category response."""


class ExpenseCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create expense."""


class ExpenseUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update expense."""


class ExpenseReadSchema(OpenSchema, BaseReadSchema):
    """Readable expense response."""


class ExpenseListParams(CRUDBaseParams):
    """Pagination + query params for expense list."""


class ExpenseListResponse(CRUDListResponse[ExpenseReadSchema]):
    """Paginated expense response."""


class CashAccountCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create cash account."""


class CashAccountUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update cash account."""


class CashAccountReadSchema(OpenSchema, BaseReadSchema):
    """Readable cash account response."""


class CashAccountListParams(CRUDBaseParams):
    """Pagination + query params for cash account list."""


class CashAccountListResponse(CRUDListResponse[CashAccountReadSchema]):
    """Paginated cash account response."""


class CashTransactionCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create cash transaction."""


class CashTransactionUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update cash transaction."""


class CashTransactionReadSchema(OpenSchema, BaseReadSchema):
    """Readable cash transaction response."""


class CashTransactionListParams(CRUDBaseParams):
    """Pagination + query params for cash transaction list."""


class CashTransactionListResponse(CRUDListResponse[CashTransactionReadSchema]):
    """Paginated cash transaction response."""


class SupplierDebtCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create supplier debt (accounts payable)."""


class SupplierDebtUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update supplier debt."""


class SupplierDebtReadSchema(OpenSchema, BaseReadSchema):
    """Readable supplier debt response."""


class SupplierDebtListParams(CRUDBaseParams):
    """Pagination + query params for supplier debt list."""


class SupplierDebtListResponse(CRUDListResponse[SupplierDebtReadSchema]):
    """Paginated supplier debt response."""


class DebtPaymentCreateSchema(OpenSchema, BaseCreateSchema):
    """Input payload to create debt payment."""


class DebtPaymentUpdateSchema(OpenSchema, BaseUpdateSchema):
    """Input payload to update debt payment."""


class DebtPaymentReadSchema(OpenSchema, BaseReadSchema):
    """Readable debt payment response."""


class DebtPaymentListParams(CRUDBaseParams):
    """Pagination + query params for debt payment list."""


class DebtPaymentListResponse(CRUDListResponse[DebtPaymentReadSchema]):
    """Paginated debt payment response."""


__all__ = [
    "ExpenseCategoryCreateSchema",
    "ExpenseCategoryUpdateSchema",
    "ExpenseCategoryReadSchema",
    "ExpenseCategoryListParams",
    "ExpenseCategoryListResponse",
    "ExpenseCreateSchema",
    "ExpenseUpdateSchema",
    "ExpenseReadSchema",
    "ExpenseListParams",
    "ExpenseListResponse",
    "CashAccountCreateSchema",
    "CashAccountUpdateSchema",
    "CashAccountReadSchema",
    "CashAccountListParams",
    "CashAccountListResponse",
    "CashTransactionCreateSchema",
    "CashTransactionUpdateSchema",
    "CashTransactionReadSchema",
    "CashTransactionListParams",
    "CashTransactionListResponse",
    "SupplierDebtCreateSchema",
    "SupplierDebtUpdateSchema",
    "SupplierDebtReadSchema",
    "SupplierDebtListParams",
    "SupplierDebtListResponse",
    "DebtPaymentCreateSchema",
    "DebtPaymentUpdateSchema",
    "DebtPaymentReadSchema",
    "DebtPaymentListParams",
    "DebtPaymentListResponse",
]
