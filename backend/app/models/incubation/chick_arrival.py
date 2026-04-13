from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    chicks_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="chick_arrivals")
    department: Mapped["Department"] = relationship("Department", back_populates="chick_arrivals")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="chick_arrivals")
    source_client: Mapped["Client | None"] = relationship("Client", back_populates="chick_arrivals")
    run: Mapped["IncubationRun | None"] = relationship("IncubationRun")
    chick_shipment: Mapped["ChickShipment | None"] = relationship("ChickShipment")

    __table_args__ = (
        CheckConstraint("chicks_count >= 0", name="ck_chick_arrival_chicks_count_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_chick_arrival_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.chicks_count).quantize(Decimal("0.01"))
