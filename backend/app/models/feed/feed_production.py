from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedProductionBatch(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_production_batches"

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
    formula_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_formulas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    started_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    finished_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_output: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    actual_output: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 2), nullable=False, default=0, server_default="0"
    )
    unit_cost: Mapped[Decimal] = mapped_column(
        Numeric(16, 4), nullable=False, default=0, server_default="0"
    )
    cost_currency_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_production_batches")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_production_batches")
    formula: Mapped["FeedFormula"] = relationship("FeedFormula", back_populates="production_batches")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[warehouse_id])
    shipments: Mapped[List["FeedProductShipment"]] = relationship(
        "FeedProductShipment",
        back_populates="production_batch",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "batch_code", name="uq_feed_production_batch_org_code"),
        CheckConstraint("planned_output >= 0", name="ck_feed_batch_planned_output_non_negative"),
        CheckConstraint("actual_output >= 0", name="ck_feed_batch_actual_output_non_negative"),
        CheckConstraint("actual_output <= planned_output", name="ck_feed_batch_actual_not_exceed_planned"),
        CheckConstraint(
            "(finished_on IS NULL) OR (started_on <= finished_on)",
            name="ck_feed_batch_period_order",
        ),
    )


class FeedProductShipment(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_product_shipments"

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
    feed_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    production_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("feed_production_batches.id", ondelete="SET NULL"),
        nullable=True,
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
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_product_shipments")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_product_shipments")
    feed_type: Mapped["FeedType"] = relationship("FeedType", back_populates="shipments")
    production_batch: Mapped["FeedProductionBatch | None"] = relationship(
        "FeedProductionBatch",
        back_populates="shipments",
    )
    client: Mapped["Client"] = relationship("Client", back_populates="feed_product_shipments")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[warehouse_id])

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "shipped_on",
            "client_id",
            "invoice_no",
            name="uq_feed_product_shipment_invoice",
        ),
        CheckConstraint("quantity >= 0", name="ck_feed_product_shipment_quantity_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_feed_product_shipment_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
