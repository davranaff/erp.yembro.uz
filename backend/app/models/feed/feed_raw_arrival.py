from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedRawArrival(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_raw_arrivals"

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
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    lot_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default="UZS",
        server_default="UZS",
    )
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    ingredient: Mapped["FeedIngredient"] = relationship("FeedIngredient")
    supplier: Mapped["Client | None"] = relationship("Client", foreign_keys=[supplier_client_id])
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[warehouse_id])

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "ingredient_id",
            "arrived_on",
            "supplier_client_id",
            "invoice_no",
            name="uq_feed_raw_arrival_invoice",
        ),
        CheckConstraint("quantity >= 0", name="ck_feed_raw_arrival_quantity_non_negative"),
        CheckConstraint(
            "unit_price IS NULL OR unit_price >= 0",
            name="ck_feed_raw_arrival_unit_price_non_negative",
        ),
    )
