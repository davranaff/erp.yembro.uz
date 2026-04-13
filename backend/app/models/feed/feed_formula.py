from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedFormula(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_formulas"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    feed_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_formulas")
    feed_type: Mapped["FeedType"] = relationship("FeedType", back_populates="formulas")
    ingredients: Mapped[List["FeedFormulaIngredient"]] = relationship(
        "FeedFormulaIngredient",
        back_populates="formula",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    production_batches: Mapped[List["FeedProductionBatch"]] = relationship(
        "FeedProductionBatch",
        back_populates="formula",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "feed_type_id",
            "code",
            name="uq_feed_formula_org_feed_type_code",
        ),
        CheckConstraint("version >= 1", name="ck_feed_formula_version_positive"),
    )


class FeedFormulaIngredient(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_formula_ingredients"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    formula_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_formulas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_per_batch: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_formula_ingredients")
    formula: Mapped["FeedFormula"] = relationship("FeedFormula", back_populates="ingredients")
    ingredient: Mapped["FeedIngredient"] = relationship("FeedIngredient", back_populates="formula_items")

    __table_args__ = (
        UniqueConstraint("organization_id", "formula_id", "ingredient_id", name="uq_feed_formula_ingredient"),
        CheckConstraint("quantity_per_batch >= 0", name="ck_feed_formula_ingredient_quantity_non_negative"),
    )
