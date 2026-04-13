from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class ExpenseCategory(Base, IDMixin, TimestampMixin):
    __tablename__ = "expense_categories"

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
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_global: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="expense_categories")
    department: Mapped["Department"] = relationship("Department", back_populates="expense_categories")
    expenses: Mapped[List["Expense"]] = relationship(
        "Expense",
        back_populates="category",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "department_id",
            "name",
            name="uq_expense_category_org_department_name",
        ),
        UniqueConstraint(
            "organization_id",
            "department_id",
            "code",
            name="uq_expense_category_org_department_code",
        ),
    )
