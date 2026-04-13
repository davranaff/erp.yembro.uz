from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class CashTransaction(Base, IDMixin, TimestampMixin):
    __tablename__ = "cash_transactions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cash_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("cash_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    expense_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("expenses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counterparty_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference_no: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="cash_transactions")
    cash_account: Mapped["CashAccount"] = relationship("CashAccount", back_populates="transactions")
    expense: Mapped["Expense | None"] = relationship("Expense", back_populates="cash_transactions", lazy="selectin")
    counterparty_client: Mapped["Client | None"] = relationship("Client", lazy="selectin")
    created_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_cash_transaction_amount_positive"),
        CheckConstraint(
            "transaction_type IN ('income', 'expense', 'transfer_in', 'transfer_out', 'adjustment')",
            name="ck_cash_transaction_type_allowed",
        ),
    )
