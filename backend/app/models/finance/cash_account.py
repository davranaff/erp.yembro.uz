from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class CashAccount(Base, IDMixin, TimestampMixin):
    __tablename__ = "cash_accounts"

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
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    opening_balance: Mapped[Decimal] = mapped_column(
        Numeric(16, 2),
        nullable=False,
        default=0,
        server_default="0",
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="cash_accounts")
    department: Mapped["Department"] = relationship("Department", back_populates="cash_accounts")
    transactions: Mapped[list["CashTransaction"]] = relationship(
        "CashTransaction",
        back_populates="cash_account",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_cash_account_org_code"),
        UniqueConstraint("organization_id", "department_id", "name", name="uq_cash_account_org_department_name"),
        CheckConstraint("opening_balance >= 0", name="ck_cash_account_opening_balance_non_negative"),
    )
