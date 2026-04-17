from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class StockMovement(Base, IDMixin, TimestampMixin):
    __tablename__ = "stock_movements"

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
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    counterparty_department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    counterparty_warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    movement_kind: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    reference_table: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference_id: Mapped[UUID] = mapped_column(nullable=False, index=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "reference_table",
            "reference_id",
            "movement_kind",
            "warehouse_id",
            "item_type",
            "item_key",
            name="uq_stock_movement_reference_kind_scope",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_movement_quantity_positive"),
        CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
            name="ck_stock_movement_item_type_allowed",
        ),
        CheckConstraint(
            "movement_kind IN ('incoming', 'outgoing', 'transfer_in', 'transfer_out', 'adjustment_in', 'adjustment_out')",
            name="ck_stock_movement_kind_allowed",
        ),
    )
