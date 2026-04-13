from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import List

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class IncubationRun(Base, IDMixin, TimestampMixin):
    __tablename__ = "incubation_runs"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("incubation_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    eggs_set: Mapped[int] = mapped_column(Integer, nullable=False)
    grade_1_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    grade_2_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bad_eggs_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chicks_hatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chicks_destroyed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="incubation_runs")
    batch: Mapped["IncubationBatch"] = relationship("IncubationBatch", back_populates="runs")
    department: Mapped["Department"] = relationship("Department", back_populates="incubation_runs")
    chick_shipments: Mapped[List["ChickShipment"]] = relationship(
        "ChickShipment",
        back_populates="run",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("batch_id", "start_date", name="uq_incubation_batch_start"),
        CheckConstraint("eggs_set >= 0", name="ck_incubation_run_eggs_set_non_negative"),
        CheckConstraint("grade_1_count >= 0", name="ck_incubation_run_grade1_non_negative"),
        CheckConstraint("grade_2_count >= 0", name="ck_incubation_run_grade2_non_negative"),
        CheckConstraint("bad_eggs_count >= 0", name="ck_incubation_run_bad_eggs_non_negative"),
        CheckConstraint("chicks_hatched >= 0", name="ck_incubation_run_chicks_hatched_non_negative"),
        CheckConstraint("chicks_destroyed >= 0", name="ck_incubation_run_chicks_destroyed_non_negative"),
        CheckConstraint(
            "grade_1_count + grade_2_count + bad_eggs_count <= eggs_set",
            name="ck_incubation_run_quality_not_greater_than_set",
        ),
        CheckConstraint(
            "chicks_hatched <= eggs_set",
            name="ck_incubation_run_hatched_not_greater_than_set",
        ),
        CheckConstraint(
            "chicks_destroyed <= chicks_hatched",
            name="ck_incubation_run_destroyed_not_greater_than_hatched",
        ),
        CheckConstraint(
            "(end_date IS NULL) OR (start_date <= end_date)",
            name="ck_incubation_run_period_order",
        ),
    )

    @hybrid_property
    def hatch_rate(self) -> Decimal:
        if self.eggs_set == 0:
            return Decimal(0)
        return Decimal(self.chicks_hatched) / Decimal(self.eggs_set)
