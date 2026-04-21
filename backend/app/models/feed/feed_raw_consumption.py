from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


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
    warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
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
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    production_batch: Mapped["FeedProductionBatch"] = relationship("FeedProductionBatch")
    ingredient: Mapped["FeedIngredient"] = relationship("FeedIngredient")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse", foreign_keys=[warehouse_id])

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "production_batch_id",
            "ingredient_id",
            name="uq_feed_raw_consumption_batch_ingredient",
        ),
        CheckConstraint("quantity > 0", name="ck_feed_raw_consumption_quantity_positive"),
    )
