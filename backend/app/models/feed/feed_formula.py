from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
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
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_formulas")
    feed_type: Mapped["FeedType"] = relationship("FeedType", back_populates="formulas")
    production_batches: Mapped[List["FeedProductionBatch"]] = relationship(
        "FeedProductionBatch",
        back_populates="formula",
        lazy="selectin",
    )
    ingredients: Mapped[List["FeedFormulaIngredient"]] = relationship(
        "FeedFormulaIngredient",
        back_populates="formula",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "feed_type_id",
            "code",
            name="uq_feed_formula_org_feed_type_code",
        ),
    )
