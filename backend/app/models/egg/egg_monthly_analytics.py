from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class EggMonthlyAnalytics(Base, IDMixin, TimestampMixin):
    __tablename__ = "egg_monthly_analytics"

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
    month_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    produced_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    broken_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    shipped_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="egg_monthly_analytics")
    department: Mapped["Department | None"] = relationship("Department", back_populates="egg_monthly_analytics")

    __table_args__ = (
        UniqueConstraint("organization_id", "department_id", "month_start", name="uq_egg_monthly_org_department_month"),
        CheckConstraint("produced_count >= 0", name="ck_egg_monthly_produced_count_non_negative"),
        CheckConstraint("broken_count >= 0", name="ck_egg_monthly_broken_count_non_negative"),
        CheckConstraint("shipped_count >= 0", name="ck_egg_monthly_shipped_count_non_negative"),
        CheckConstraint("rejected_count >= 0", name="ck_egg_monthly_rejected_count_non_negative"),
        CheckConstraint("revenue >= 0", name="ck_egg_monthly_revenue_non_negative"),
    )

    def diff_vs_previous(self, previous: "EggMonthlyAnalytics | None") -> dict[str, int | Decimal]:
        if previous is None:
            return {
                "produced_diff": 0,
                "shipped_diff": 0,
                "broken_diff": 0,
                "revenue_diff": 0,
            }
        return {
            "produced_diff": self.produced_count - previous.produced_count,
            "shipped_diff": self.shipped_count - previous.shipped_count,
            "broken_diff": self.broken_count - previous.broken_count,
            "revenue_diff": self.revenue - previous.revenue,
        }
