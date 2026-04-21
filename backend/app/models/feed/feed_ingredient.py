from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedIngredient(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_ingredients"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_ingredients")
    formula_items: Mapped[List["FeedFormulaIngredient"]] = relationship(
        "FeedFormulaIngredient",
        back_populates="ingredient",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_feed_ingredient_org_name"),
        UniqueConstraint("organization_id", "code", name="uq_feed_ingredient_org_code"),
    )
