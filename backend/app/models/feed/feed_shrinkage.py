from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base, IDMixin, TimestampMixin


class FeedShrinkageProfile(Base, IDMixin, TimestampMixin):
    """Rule describing how fast a feed lot loses weight at storage."""

    __tablename__ = "feed_shrinkage_profiles"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(24), nullable=False)
    ingredient_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("feed_ingredients.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    feed_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("feed_types.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    period_days: Mapped[int] = mapped_column(Integer, nullable=False)
    percent_per_period: Mapped[Decimal] = mapped_column(Numeric(6, 3), nullable=False)
    max_total_percent: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    stop_after_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    starts_after_days: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "target_type IN ('ingredient', 'feed_type')",
            name="ck_feed_shrinkage_profile_target_type",
        ),
        CheckConstraint(
            "(target_type = 'ingredient' AND ingredient_id IS NOT NULL "
            "AND feed_type_id IS NULL) "
            "OR (target_type = 'feed_type' AND feed_type_id IS NOT NULL "
            "AND ingredient_id IS NULL)",
            name="ck_feed_shrinkage_profile_target_exactly_one",
        ),
        CheckConstraint(
            "period_days > 0",
            name="ck_feed_shrinkage_profile_period_positive",
        ),
        CheckConstraint(
            "percent_per_period >= 0 AND percent_per_period <= 100",
            name="ck_feed_shrinkage_profile_percent_bounded",
        ),
        CheckConstraint(
            "max_total_percent IS NULL OR "
            "(max_total_percent >= 0 AND max_total_percent <= 100)",
            name="ck_feed_shrinkage_profile_max_percent_bounded",
        ),
        CheckConstraint(
            "stop_after_days IS NULL OR stop_after_days > 0",
            name="ck_feed_shrinkage_profile_stop_after_positive",
        ),
        CheckConstraint(
            "starts_after_days >= 0",
            name="ck_feed_shrinkage_profile_starts_after_non_negative",
        ),
    )


class FeedLotShrinkageState(Base, IDMixin, TimestampMixin):
    """Running tally of how much a single feed lot has lost to shrinkage."""

    __tablename__ = "feed_lot_shrinkage_state"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    lot_type: Mapped[str] = mapped_column(String(24), nullable=False)
    lot_id: Mapped[UUID] = mapped_column(nullable=False)
    profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("feed_shrinkage_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    initial_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    accumulated_loss: Mapped[Decimal] = mapped_column(
        Numeric(16, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    last_applied_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_frozen: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    __table_args__ = (
        CheckConstraint(
            "lot_type IN ('raw_arrival', 'production_batch')",
            name="ck_feed_lot_shrinkage_state_lot_type",
        ),
        CheckConstraint(
            "initial_quantity > 0",
            name="ck_feed_lot_shrinkage_state_initial_positive",
        ),
        CheckConstraint(
            "accumulated_loss >= 0 AND accumulated_loss <= initial_quantity",
            name="ck_feed_lot_shrinkage_state_loss_bounded",
        ),
        UniqueConstraint(
            "lot_type", "lot_id", name="uq_feed_lot_shrinkage_state_lot"
        ),
    )
