from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedMonthlyAnalytics(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_monthly_analytics"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    feed_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("feed_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    month_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    raw_arrivals_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0, server_default="0")
    raw_consumptions_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0, server_default="0")
    produced_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0, server_default="0")
    shipped_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0, server_default="0")
    shipped_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    purchased_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0, server_default="0")
    quality_passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quality_failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quality_pending_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization")
    department: Mapped["Department | None"] = relationship("Department")
    feed_type: Mapped["FeedType | None"] = relationship("FeedType")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "department_id",
            "feed_type_id",
            "month_start",
            name="uq_feed_monthly_org_dept_type_month",
        ),
        CheckConstraint("raw_arrivals_kg >= 0", name="ck_feed_monthly_raw_arrivals_non_negative"),
        CheckConstraint("raw_consumptions_kg >= 0", name="ck_feed_monthly_raw_consumptions_non_negative"),
        CheckConstraint("produced_kg >= 0", name="ck_feed_monthly_produced_non_negative"),
        CheckConstraint("shipped_kg >= 0", name="ck_feed_monthly_shipped_non_negative"),
        CheckConstraint("shipped_amount >= 0", name="ck_feed_monthly_shipped_amount_non_negative"),
        CheckConstraint("purchased_amount >= 0", name="ck_feed_monthly_purchased_amount_non_negative"),
        CheckConstraint("quality_passed_count >= 0", name="ck_feed_monthly_quality_passed_non_negative"),
        CheckConstraint("quality_failed_count >= 0", name="ck_feed_monthly_quality_failed_non_negative"),
        CheckConstraint("quality_pending_count >= 0", name="ck_feed_monthly_quality_pending_non_negative"),
    )
