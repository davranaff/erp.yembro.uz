from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class FeedConsumption(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_consumptions"

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
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feed_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    consumed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_feed_consumption_quantity_positive"),
    )
