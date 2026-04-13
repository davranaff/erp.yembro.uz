from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class IncubationMonthlyAnalytics(Base, IDMixin, TimestampMixin):
    __tablename__ = "incubation_monthly_analytics"

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
    eggs_arrived: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade1_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade2_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_eggs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chicks_hatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chicks_shipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="incubation_monthly_analytics")
    department: Mapped["Department | None"] = relationship("Department", back_populates="incubation_monthly_analytics")

    __table_args__ = (
        UniqueConstraint("organization_id", "department_id", "month_start", name="uq_incubation_monthly_org_department_month"),
        CheckConstraint("eggs_arrived >= 0", name="ck_incubation_monthly_eggs_arrived_non_negative"),
        CheckConstraint("grade1_count >= 0", name="ck_incubation_monthly_grade1_non_negative"),
        CheckConstraint("grade2_count >= 0", name="ck_incubation_monthly_grade2_non_negative"),
        CheckConstraint("bad_eggs_count >= 0", name="ck_incubation_monthly_bad_eggs_non_negative"),
        CheckConstraint("chicks_hatched >= 0", name="ck_incubation_monthly_chicks_hatched_non_negative"),
        CheckConstraint("chicks_shipped >= 0", name="ck_incubation_monthly_chicks_shipped_non_negative"),
    )

    def diff_vs_previous(self, previous: "IncubationMonthlyAnalytics | None") -> dict[str, int]:
        if previous is None:
            return {
                "eggs_arrived_diff": 0,
                "grade1_diff": 0,
                "grade2_diff": 0,
                "bad_eggs_diff": 0,
                "chicks_hatched_diff": 0,
                "chicks_shipped_diff": 0,
            }
        return {
            "eggs_arrived_diff": self.eggs_arrived - previous.eggs_arrived,
            "grade1_diff": self.grade1_count - previous.grade1_count,
            "grade2_diff": self.grade2_count - previous.grade2_count,
            "bad_eggs_diff": self.bad_eggs_count - previous.bad_eggs_count,
            "chicks_hatched_diff": self.chicks_hatched - previous.chicks_hatched,
            "chicks_shipped_diff": self.chicks_shipped - previous.chicks_shipped,
        }
