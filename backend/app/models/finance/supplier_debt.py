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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SupplierDebt(Base, IDMixin, TimestampMixin):
    """Accounts payable — what the organization owes an external supplier.

    Mirrors ``ClientDebt`` (which tracks receivables) but from the other side:
    ``client_id`` here references the supplier (the ``clients`` table stores
    both customers and suppliers).
    """

    __tablename__ = "supplier_debts"

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
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_total: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    issued_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="open", server_default="open", index=True)
    posting_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="posted",
        server_default="posted",
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    department: Mapped["Department"] = relationship("Department", lazy="selectin")
    supplier: Mapped["Client"] = relationship("Client", lazy="selectin")
    payments: Mapped[list["DebtPayment"]] = relationship(
        "DebtPayment",
        back_populates="supplier_debt",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "department_id",
            "client_id",
            "item_key",
            "issued_on",
            name="uq_supplier_debt_scope_item_date",
        ),
        CheckConstraint("quantity > 0", name="ck_supplier_debt_quantity_positive"),
        CheckConstraint("amount_total >= 0", name="ck_supplier_debt_amount_total_non_negative"),
        CheckConstraint("amount_paid >= 0", name="ck_supplier_debt_amount_paid_non_negative"),
        CheckConstraint("amount_paid <= amount_total", name="ck_supplier_debt_amount_paid_not_exceed_total"),
        CheckConstraint("(due_on IS NULL) OR (due_on >= issued_on)", name="ck_supplier_debt_due_not_before_issued"),
        CheckConstraint(
            "status IN ('open', 'partially_paid', 'closed', 'cancelled')",
            name="ck_supplier_debt_status",
        ),
    )
