from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class ChickArrival(Base, IDMixin, TimestampMixin):
    __tablename__ = "chick_arrivals"

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
    source_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("incubation_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chick_shipment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chick_shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    chicks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("chicks_count >= 0", name="ck_chick_arrival_chicks_count_non_negative"),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_chick_arrival_unit_price_non_negative",
        ),
    )
