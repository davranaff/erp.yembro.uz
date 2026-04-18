from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class StockTakeLine(Base, IDMixin, TimestampMixin):
    __tablename__ = "stock_take_lines"

    stock_take_id: Mapped[UUID] = mapped_column(
        ForeignKey("stock_takes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    expected_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    counted_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "stock_take_id",
            "item_type",
            "item_key",
            name="uq_stock_take_line_take_item",
        ),
        CheckConstraint(
            "item_type IN ('egg', 'chick', 'feed', 'feed_raw', 'medicine', 'semi_product')",
            name="ck_stock_take_line_item_type_allowed",
        ),
        CheckConstraint("expected_quantity >= 0", name="ck_stock_take_line_expected_non_negative"),
        CheckConstraint("counted_quantity >= 0", name="ck_stock_take_line_counted_non_negative"),
    )
