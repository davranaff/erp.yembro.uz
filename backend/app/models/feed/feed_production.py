from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
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
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_raw_arrivals")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_raw_arrivals")
    ingredient: Mapped["FeedIngredient"] = relationship("FeedIngredient", back_populates="arrivals")
    supplier_client: Mapped["Client | None"] = relationship("Client", back_populates="feed_raw_arrivals")

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
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_feed_raw_arrival_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))


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
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_production_batches")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_production_batches")
    formula: Mapped["FeedFormula"] = relationship("FeedFormula", back_populates="production_batches")
    raw_consumptions: Mapped[List["FeedRawConsumption"]] = relationship(
        "FeedRawConsumption",
        back_populates="production_batch",
        lazy="selectin",
    )
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


class FeedRawConsumption(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_raw_consumptions"

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
    production_batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_production_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    consumed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_raw_consumptions")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_raw_consumptions")
    production_batch: Mapped["FeedProductionBatch"] = relationship("FeedProductionBatch", back_populates="raw_consumptions")
    ingredient: Mapped["FeedIngredient"] = relationship("FeedIngredient", back_populates="consumptions")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "production_batch_id",
            "ingredient_id",
            name="uq_feed_raw_consumption_batch_ingredient",
        ),
        CheckConstraint("quantity > 0", name="ck_feed_raw_consumption_quantity_positive"),
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
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_product_shipments")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_product_shipments")
    feed_type: Mapped["FeedType"] = relationship("FeedType", back_populates="shipments")
    production_batch: Mapped["FeedProductionBatch | None"] = relationship(
        "FeedProductionBatch",
        back_populates="shipments",
    )
    client: Mapped["Client"] = relationship("Client", back_populates="feed_product_shipments")

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
