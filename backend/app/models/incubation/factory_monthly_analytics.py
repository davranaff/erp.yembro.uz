from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FactoryMonthlyAnalytics(Base, IDMixin, TimestampMixin):
    __tablename__ = "factory_monthly_analytics"

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
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    month_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    chicks_arrived: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    feed_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    feed_quantity_unit: Mapped[str] = mapped_column(String(16), nullable=False, default="kg", server_default="kg")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medicines_arrived: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_monthly_analytics")
    department: Mapped["Department | None"] = relationship("Department", back_populates="factory_monthly_analytics")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="factory_monthly_analytics")

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "department_id",
            "poultry_type_id",
            "month_start",
            name="uq_factory_monthly_org_department_poultry_month",
        ),
        CheckConstraint("chicks_arrived >= 0", name="ck_factory_monthly_chicks_arrived_non_negative"),
        CheckConstraint("feed_quantity >= 0", name="ck_factory_monthly_feed_quantity_non_negative"),
        CheckConstraint("medicines_arrived >= 0", name="ck_factory_monthly_medicines_arrived_non_negative"),
    )

    def diff_vs_previous(self, previous: "FactoryMonthlyAnalytics | None") -> dict[str, int | Decimal]:
        if previous is None:
            return {
                "chicks_arrived_diff": 0,
                "feed_quantity_diff": Decimal("0"),
                "medicines_arrived_diff": Decimal("0"),
            }
        return {
            "chicks_arrived_diff": self.chicks_arrived - previous.chicks_arrived,
            "feed_quantity_diff": self.feed_quantity - previous.feed_quantity,
            "medicines_arrived_diff": self.medicines_arrived - previous.medicines_arrived,
        }
