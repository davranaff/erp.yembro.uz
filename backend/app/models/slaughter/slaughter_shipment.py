from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SlaughterSemiProductShipment(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_semi_product_shipments"

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
    semi_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("slaughter_semi_products.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    client_id: Mapped[UUID] = mapped_column(
        ForeignKey("clients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipped_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="slaughter_semi_product_shipments")
    department: Mapped["Department"] = relationship("Department", back_populates="slaughter_semi_product_shipments")
    semi_product: Mapped["SlaughterSemiProduct"] = relationship(
        "SlaughterSemiProduct",
        back_populates="shipments",
    )
    client: Mapped["Client"] = relationship("Client", back_populates="slaughter_semi_product_shipments")
    created_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")

    __table_args__ = (
        UniqueConstraint("organization_id", "shipped_on", "client_id", "invoice_no", name="uq_slaughter_semi_product_shipment_invoice"),
        CheckConstraint("quantity > 0", name="ck_slaughter_shipment_quantity_positive"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_slaughter_shipment_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
