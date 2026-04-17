from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class SlaughterArrival(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_arrivals"

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
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chick_arrival_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chick_arrivals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    birds_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    average_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "arrived_on",
            "supplier_client_id",
            "invoice_no",
            name="uq_slaughter_arrival_invoice",
        ),
        CheckConstraint("birds_count >= 0", name="ck_slaughter_arrival_birds_count_non_negative"),
        CheckConstraint(
            "average_weight_kg IS NULL OR average_weight_kg >= 0",
            name="ck_slaughter_arrival_avg_weight_non_negative",
        ),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_slaughter_arrival_unit_price_non_negative",
        ),
    )
