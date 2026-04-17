from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FactoryVaccinationPlan(Base, IDMixin, TimestampMixin):
    """Календарь вакцинации по партии на фабрике."""

    __tablename__ = "factory_vaccination_plans"

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
    flock_id: Mapped[UUID] = mapped_column(
        ForeignKey("factory_flocks.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medicine_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicine_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    day_of_life: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_completed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false",
    )
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_vaccination_plans")
    department: Mapped["Department"] = relationship("Department", back_populates="factory_vaccination_plans")
    flock: Mapped["FactoryFlock"] = relationship("FactoryFlock", back_populates="vaccination_plans")
    medicine_type: Mapped["MedicineType"] = relationship("MedicineType")

    __table_args__ = (
        CheckConstraint("day_of_life > 0", name="ck_factory_vaccination_plan_day_positive"),
    )
