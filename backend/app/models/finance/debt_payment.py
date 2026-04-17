from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class DebtPayment(Base, IDMixin, TimestampMixin):
    """Single payment against a debt (receivable or payable).

    Polymorphic: exactly one of ``client_debt_id`` (AR — incoming payment from
    a customer) or ``supplier_debt_id`` (AP — outgoing payment to a supplier)
    must be set. ``direction`` mirrors this for query convenience.

    Optionally linked to a ``CashTransaction`` to keep the cash account balance
    in sync; the transaction is created/updated automatically by the service.
    """

    __tablename__ = "debt_payments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_debt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("client_debts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    supplier_debt_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("supplier_debts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    direction: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    method: Mapped[str] = mapped_column(
        String(24), nullable=False, default="cash", server_default="cash", index=True,
    )
    reference_no: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    cash_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cash_accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cash_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cash_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    department: Mapped["Department"] = relationship("Department", lazy="selectin")
    client_debt: Mapped["ClientDebt | None"] = relationship(
        "ClientDebt",
        back_populates="payments",
        lazy="selectin",
    )
    supplier_debt: Mapped["SupplierDebt | None"] = relationship(
        "SupplierDebt",
        back_populates="payments",
        lazy="selectin",
    )
    cash_account: Mapped["CashAccount | None"] = relationship("CashAccount", lazy="selectin")
    cash_transaction: Mapped["CashTransaction | None"] = relationship("CashTransaction", lazy="selectin")
    created_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debt_payment_amount_positive"),
        CheckConstraint(
            "direction IN ('incoming', 'outgoing')",
            name="ck_debt_payment_direction_allowed",
        ),
        CheckConstraint(
            "method IN ('cash', 'bank', 'card', 'transfer', 'offset', 'other')",
            name="ck_debt_payment_method_allowed",
        ),
        CheckConstraint(
            "(client_debt_id IS NOT NULL AND supplier_debt_id IS NULL) OR "
            "(client_debt_id IS NULL AND supplier_debt_id IS NOT NULL)",
            name="ck_debt_payment_exactly_one_parent",
        ),
        CheckConstraint(
            "(direction = 'incoming' AND client_debt_id IS NOT NULL) OR "
            "(direction = 'outgoing' AND supplier_debt_id IS NOT NULL)",
            name="ck_debt_payment_direction_matches_parent",
        ),
    )
