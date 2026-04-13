from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Expense(Base, IDMixin, TimestampMixin):
    __tablename__ = "expenses"

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
    category_id: Mapped[UUID] = mapped_column(
        ForeignKey("expense_categories.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    item: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    expense_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="expenses")
    department: Mapped["Department"] = relationship("Department", back_populates="expenses")
    category: Mapped["ExpenseCategory"] = relationship("ExpenseCategory", back_populates="expenses")
    created_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")
    cash_transactions: Mapped[list["CashTransaction"]] = relationship(
        "CashTransaction",
        back_populates="expense",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "department_id", "expense_date", "category_id", "title", name="uq_expense_org_department_date_category_title"),
        CheckConstraint("quantity IS NULL OR quantity >= 0", name="ck_expense_quantity_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_expense_unit_price_non_negative"),
        CheckConstraint("amount >= 0", name="ck_expense_amount_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is not None and self.quantity is not None:
            return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
        return self.amount
