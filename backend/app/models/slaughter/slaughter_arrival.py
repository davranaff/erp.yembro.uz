from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    factory_shipment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("factory_shipments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    birds_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    arrival_total_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    arrival_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    arrival_currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    arrival_invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="slaughter_arrivals"
    )
    department: Mapped["Department"] = relationship(
        "Department", back_populates="slaughter_arrivals"
    )
    factory_shipment: Mapped["FactoryShipment | None"] = relationship(
        "FactoryShipment", lazy="selectin"
    )
    supplier_client: Mapped["Client | None"] = relationship("Client", lazy="selectin")
    poultry_type: Mapped["PoultryType | None"] = relationship(
        "PoultryType", back_populates="slaughter_arrivals"
    )
    processings: Mapped[list["SlaughterProcessing"]] = relationship(
        "SlaughterProcessing",
        back_populates="arrival",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "source_type IN ('factory', 'external')",
            name="ck_slaughter_arrival_source_type",
        ),
        CheckConstraint(
            "(source_type = 'factory' AND factory_shipment_id IS NOT NULL AND supplier_client_id IS NULL) OR "
            "(source_type = 'external' AND supplier_client_id IS NOT NULL AND factory_shipment_id IS NULL)",
            name="ck_slaughter_arrival_source_exactly_one",
        ),
        CheckConstraint("birds_received >= 0", name="ck_slaughter_arrival_birds_received_non_negative"),
        CheckConstraint(
            "arrival_total_weight_kg IS NULL OR arrival_total_weight_kg >= 0",
            name="ck_slaughter_arrival_total_weight_non_negative",
        ),
        CheckConstraint(
            "arrival_unit_price IS NULL OR arrival_unit_price >= 0",
            name="ck_slaughter_arrival_unit_price_non_negative",
        ),
    )

    @property
    def effective_amount(self) -> Decimal:
        if self.arrival_unit_price is None or self.arrival_total_weight_kg is None:
            return Decimal(0)
        return (self.arrival_unit_price * self.arrival_total_weight_kg).quantize(Decimal("0.01"))
