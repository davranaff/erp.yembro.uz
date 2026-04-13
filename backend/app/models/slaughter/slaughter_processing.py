from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SlaughterProcessing(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_processings"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    arrival_id: Mapped[UUID] = mapped_column(
        ForeignKey("slaughter_arrivals.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    processed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    birds_processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_sort_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    second_sort_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    first_sort_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    second_sort_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    bad_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    processed_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="slaughter_processings")
    department: Mapped["Department"] = relationship("Department", back_populates="slaughter_processings")
    arrival: Mapped["SlaughterArrival"] = relationship("SlaughterArrival", back_populates="processings")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="slaughter_processings")
    processed_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")
    semifinished_items: Mapped[list["SlaughterSemiProduct"]] = relationship(
        "SlaughterSemiProduct",
        back_populates="processing",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("arrival_id", "processed_on", name="uq_slaughter_processing_arrival_date"),
        CheckConstraint("birds_processed >= 0", name="ck_slaughter_processing_birds_processed_non_negative"),
        CheckConstraint("first_sort_count >= 0", name="ck_slaughter_processing_first_sort_non_negative"),
        CheckConstraint("second_sort_count >= 0", name="ck_slaughter_processing_second_sort_non_negative"),
        CheckConstraint("bad_count >= 0", name="ck_slaughter_processing_bad_count_non_negative"),
        CheckConstraint(
            "first_sort_count + second_sort_count + bad_count <= birds_processed",
            name="ck_slaughter_processing_quality_not_exceed_processed",
        ),
        CheckConstraint(
            "first_sort_weight_kg IS NULL OR first_sort_weight_kg >= 0",
            name="ck_slaughter_processing_first_sort_weight_non_negative",
        ),
        CheckConstraint(
            "second_sort_weight_kg IS NULL OR second_sort_weight_kg >= 0",
            name="ck_slaughter_processing_second_sort_weight_non_negative",
        ),
        CheckConstraint(
            "bad_weight_kg IS NULL OR bad_weight_kg >= 0",
            name="ck_slaughter_processing_bad_weight_non_negative",
        ),
    )

    @property
    def total_weight(self) -> Decimal:
        total = Decimal(0)
        for value in (self.first_sort_weight_kg, self.second_sort_weight_kg, self.bad_weight_kg):
            if value is not None:
                total += value
        return total
