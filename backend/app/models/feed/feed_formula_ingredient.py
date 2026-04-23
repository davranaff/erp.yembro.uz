"""Состав формулы корма.

Одна запись этой таблицы = «чтобы произвести одну единицу готового
корма по данной формуле, нужно N единиц такого-то ингредиента».
Сервис производства умножает эти пропорции на ``actual_output`` партии
и автоматически создаёт ``feed_raw_consumptions``.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedFormulaIngredient(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_formula_ingredients"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    formula_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_formulas.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ingredient_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_ingredients.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Сколько ингредиента нужно на одну единицу (обычно 1 кг) готового корма.
    # Хранится как Decimal(12,6), чтобы поддерживать точные доли типа 0.45.
    quantity_per_unit: Mapped[Decimal] = mapped_column(
        Numeric(12, 6), nullable=False
    )
    unit: Mapped[str] = mapped_column(
        String(20), nullable=False, default="kg", server_default="kg"
    )
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    formula: Mapped["FeedFormula"] = relationship(
        "FeedFormula",
        back_populates="ingredients",
    )
    ingredient: Mapped["FeedIngredient"] = relationship(
        "FeedIngredient",
        back_populates="formula_items",
    )

    __table_args__ = (
        UniqueConstraint(
            "formula_id",
            "ingredient_id",
            name="uq_feed_formula_ingredient_formula_ingredient",
        ),
        CheckConstraint(
            "quantity_per_unit > 0",
            name="ck_feed_formula_ingredient_qty_positive",
        ),
    )
