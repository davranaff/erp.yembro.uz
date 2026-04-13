from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedArrival(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_arrivals"

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
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    invoice_no: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_arrivals")
    department: Mapped["Department"] = relationship("Department", back_populates="feed_arrivals")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="feed_arrivals")
    feed_type: Mapped["FeedType"] = relationship("FeedType", back_populates="feed_arrivals")
    supplier_client: Mapped["Client | None"] = relationship("Client", back_populates="feed_arrivals")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "arrived_on",
            "supplier_client_id",
            "invoice_no",
            name="uq_feed_arrival_invoice",
        ),
        CheckConstraint("quantity >= 0", name="ck_feed_arrival_quantity_non_negative"),
        CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_feed_arrival_unit_price_non_negative"),
    )

    @hybrid_property
    def effective_amount(self) -> Decimal:
        if self.unit_price is None:
            return Decimal(0)
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))
