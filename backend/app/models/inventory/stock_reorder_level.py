from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class StockReorderLevel(Base, IDMixin, TimestampMixin):
    __tablename__ = "stock_reorder_levels"

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
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    min_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    max_quantity: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    reorder_quantity: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "warehouse_id",
            "item_type",
            "item_key",
            name="uq_stock_reorder_level_scope_item",
        ),
        CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
            name="ck_stock_reorder_level_item_type_allowed",
        ),
        CheckConstraint("min_quantity >= 0", name="ck_stock_reorder_level_min_non_negative"),
        CheckConstraint(
            "max_quantity IS NULL OR max_quantity >= min_quantity",
            name="ck_stock_reorder_level_max_gte_min",
        ),
        CheckConstraint(
            "reorder_quantity IS NULL OR reorder_quantity >= 0",
            name="ck_stock_reorder_level_reorder_non_negative",
        ),
    )
