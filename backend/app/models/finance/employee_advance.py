from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class EmployeeAdvance(Base, IDMixin, TimestampMixin):
    __tablename__ = "employee_advances"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    employee_id: Mapped[UUID] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_issued: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    issued_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open", index=True
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", lazy="selectin")
    department: Mapped["Department | None"] = relationship("Department", lazy="selectin")
    employee: Mapped["Employee"] = relationship(
        "Employee", foreign_keys=[employee_id], lazy="selectin"
    )
    created_by_employee: Mapped["Employee | None"] = relationship(
        "Employee", foreign_keys=[created_by], lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("amount_issued > 0", name="ck_employee_advances_amount_positive"),
        CheckConstraint(
            "status IN ('open', 'reconciled', 'cancelled')",
            name="ck_employee_advances_status",
        ),
    )
