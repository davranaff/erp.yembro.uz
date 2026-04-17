from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class EggShipment(Base, IDMixin, TimestampMixin):
    __tablename__ = "egg_shipments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    production_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("egg_production.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipped_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    eggs_count: Mapped[int] = mapped_column(Integer, nullable=False)
    eggs_broken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="egg_shipments")
    production: Mapped["EggProduction | None"] = relationship(
        "EggProduction",
        back_populates="shipments",
    )
    department: Mapped["Department"] = relationship("Department", back_populates="egg_shipments")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    client: Mapped["Client"] = relationship("Client", back_populates="egg_shipments")

    __table_args__ = (
        UniqueConstraint("organization_id", "shipped_on", "client_id", "invoice_no", name="uq_egg_shipment_invoice"),
        CheckConstraint("eggs_count >= 0", name="ck_egg_shipment_eggs_count_non_negative"),
        CheckConstraint("eggs_broken >= 0", name="ck_egg_shipment_eggs_broken_non_negative"),
        CheckConstraint("unit_price >= 0", name="ck_egg_shipment_unit_price_non_negative"),
        CheckConstraint("eggs_broken <= eggs_count", name="ck_egg_shipment_broken_not_greater_count"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.eggs_count).quantize(Decimal("0.01"))
