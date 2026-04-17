from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SlaughterMonthlyAnalytics(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_monthly_analytics"

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
    birds_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    birds_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_sort_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    second_sort_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_sort_weight_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    second_sort_weight_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    bad_weight_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    shipped_quantity_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    shipped_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    purchased_amount: Mapped[Decimal] = mapped_column(Numeric(16, 2), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="slaughter_monthly_analytics"
    )
    department: Mapped["Department | None"] = relationship(
        "Department", back_populates="slaughter_monthly_analytics"
    )
    poultry_type: Mapped["PoultryType | None"] = relationship(
        "PoultryType", back_populates="slaughter_monthly_analytics"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "department_id",
            "poultry_type_id",
            "month_start",
            name="uq_slaughter_monthly_org_department_poultry_month",
        ),
        CheckConstraint("birds_received >= 0", name="ck_slaughter_monthly_birds_received_non_negative"),
        CheckConstraint("birds_processed >= 0", name="ck_slaughter_monthly_birds_processed_non_negative"),
        CheckConstraint(
            "birds_processed <= birds_received",
            name="ck_slaughter_monthly_processed_not_exceed_received",
        ),
        CheckConstraint("first_sort_count >= 0", name="ck_slaughter_monthly_first_sort_count_non_negative"),
        CheckConstraint("second_sort_count >= 0", name="ck_slaughter_monthly_second_sort_count_non_negative"),
        CheckConstraint("bad_count >= 0", name="ck_slaughter_monthly_bad_count_non_negative"),
        CheckConstraint(
            "first_sort_weight_kg >= 0",
            name="ck_slaughter_monthly_first_sort_weight_non_negative",
        ),
        CheckConstraint(
            "second_sort_weight_kg >= 0",
            name="ck_slaughter_monthly_second_sort_weight_non_negative",
        ),
        CheckConstraint("bad_weight_kg >= 0", name="ck_slaughter_monthly_bad_weight_non_negative"),
        CheckConstraint(
            "shipped_quantity_kg >= 0",
            name="ck_slaughter_monthly_shipped_quantity_non_negative",
        ),
        CheckConstraint("shipped_amount >= 0", name="ck_slaughter_monthly_shipped_amount_non_negative"),
        CheckConstraint(
            "purchased_amount >= 0",
            name="ck_slaughter_monthly_purchased_amount_non_negative",
        ),
    )

    def diff_vs_previous(
        self, previous: "SlaughterMonthlyAnalytics | None"
    ) -> dict[str, int | Decimal]:
        if previous is None:
            return {
                "birds_received_diff": 0,
                "birds_processed_diff": 0,
                "shipped_quantity_diff": Decimal("0"),
                "shipped_amount_diff": Decimal("0"),
                "purchased_amount_diff": Decimal("0"),
            }
        return {
            "birds_received_diff": self.birds_received - previous.birds_received,
            "birds_processed_diff": self.birds_processed - previous.birds_processed,
            "shipped_quantity_diff": self.shipped_quantity_kg - previous.shipped_quantity_kg,
            "shipped_amount_diff": self.shipped_amount - previous.shipped_amount,
            "purchased_amount_diff": self.purchased_amount - previous.purchased_amount,
        }

    @property
    def first_sort_rate(self) -> Decimal:
        total = self.first_sort_count + self.second_sort_count + self.bad_count
        if total == 0:
            return Decimal("0")
        return (Decimal(self.first_sort_count) / Decimal(total) * Decimal(100)).quantize(Decimal("0.01"))
