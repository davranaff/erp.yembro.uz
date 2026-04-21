from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FactoryShipment(Base, IDMixin, TimestampMixin):
    """Отгрузка бройлеров с фабрики."""

    __tablename__ = "factory_shipments"

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
    warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    flock_id: Mapped[UUID] = mapped_column(
        ForeignKey("factory_flocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipped_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    birds_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_weight_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    destination_department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
    )
    received_quantity: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 3), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="sent", server_default="sent", index=True
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_shipments")
    department: Mapped["Department"] = relationship("Department", back_populates="factory_shipments")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    flock: Mapped["FactoryFlock"] = relationship("FactoryFlock", back_populates="shipments")
    client: Mapped["Client"] = relationship("Client", back_populates="factory_shipments")

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "shipped_on", "client_id", "invoice_no",
            name="uq_factory_shipment_invoice",
        ),
        CheckConstraint("birds_count > 0", name="ck_factory_shipment_birds_count_positive"),
        CheckConstraint("total_weight_kg > 0", name="ck_factory_shipment_weight_positive"),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_factory_shipment_unit_price_non_negative",
        ),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.total_weight_kg).quantize(Decimal("0.01"))
