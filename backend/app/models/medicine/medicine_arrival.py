from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class MedicineArrival(Base, IDMixin, TimestampMixin):
    __tablename__ = "medicine_arrivals"

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
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    medicine_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicine_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "arrived_on",
            "supplier_client_id",
            "invoice_no",
            name="uq_medicine_arrival_invoice",
        ),
        CheckConstraint("quantity >= 0", name="ck_medicine_arrival_quantity_non_negative"),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_medicine_arrival_unit_price_non_negative",
        ),
    )
