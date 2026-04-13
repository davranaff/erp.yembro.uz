from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SlaughterSemiProduct(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_semi_products"

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
    processing_id: Mapped[UUID] = mapped_column(
        ForeignKey("slaughter_processings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    part_name: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    quality: Mapped[str] = mapped_column(String(30), nullable=False, default="first")
    produced_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="slaughter_semi_products")
    department: Mapped["Department"] = relationship("Department", back_populates="slaughter_semi_products")
    processing: Mapped["SlaughterProcessing"] = relationship("SlaughterProcessing", back_populates="semifinished_items")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="slaughter_semi_products")
    shipments: Mapped[list["SlaughterSemiProductShipment"]] = relationship(
        "SlaughterSemiProductShipment",
        back_populates="semi_product",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "processing_id", "code", name="uq_slaughter_semi_product_org_processing_code"),
        CheckConstraint("quality IN ('first', 'second', 'mixed', 'byproduct')", name="ck_slaughter_semi_product_quality"),
        CheckConstraint("quantity > 0", name="ck_slaughter_semi_product_quantity_positive"),
        CheckConstraint("produced_on IS NOT NULL", name="ck_slaughter_semi_product_produced_on_required"),
    )
