from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class ChickShipment(Base, IDMixin, TimestampMixin):
    __tablename__ = "chick_shipments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("incubation_runs.id", ondelete="SET NULL"),
        nullable=True,
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
    shipped_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    chicks_count: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="chick_shipments")
    run: Mapped["IncubationRun | None"] = relationship("IncubationRun", back_populates="chick_shipments")
    department: Mapped["Department"] = relationship("Department", back_populates="chick_shipments")
    client: Mapped["Client"] = relationship("Client", back_populates="chick_shipments")

    __table_args__ = (
        UniqueConstraint("organization_id", "shipped_on", "client_id", "invoice_no", name="uq_chick_shipment_invoice"),
        CheckConstraint("chicks_count >= 0", name="ck_chick_shipment_chicks_count_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_chick_shipment_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.chicks_count).quantize(Decimal("0.01"))
