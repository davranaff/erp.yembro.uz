from __future__ import annotations

from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FactoryFlock(Base, IDMixin, TimestampMixin):
    """Партия птенцов на фабрике (бройлерная ферма)."""

    __tablename__ = "factory_flocks"

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
    warehouse_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chick_arrival_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("chick_arrivals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    flock_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    initial_count: Mapped[int] = mapped_column(Integer, nullable=False)
    current_count: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active", server_default="active",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true",
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_flocks")
    department: Mapped["Department"] = relationship("Department", back_populates="factory_flocks")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType")
    chick_arrival: Mapped["ChickArrival | None"] = relationship("ChickArrival")
    daily_logs: Mapped[List["FactoryDailyLog"]] = relationship(
        "FactoryDailyLog",
        back_populates="flock",
        lazy="selectin",
    )
    shipments: Mapped[List["FactoryShipment"]] = relationship(
        "FactoryShipment",
        back_populates="flock",
        lazy="selectin",
    )
    medicine_usages: Mapped[List["FactoryMedicineUsage"]] = relationship(
        "FactoryMedicineUsage",
        back_populates="flock",
        lazy="selectin",
    )
    vaccination_plans: Mapped[List["FactoryVaccinationPlan"]] = relationship(
        "FactoryVaccinationPlan",
        back_populates="flock",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "flock_code", name="uq_factory_flock_org_code"),
        CheckConstraint("initial_count > 0", name="ck_factory_flock_initial_count_positive"),
        CheckConstraint("current_count >= 0", name="ck_factory_flock_current_count_non_negative"),
        CheckConstraint("current_count <= initial_count", name="ck_factory_flock_current_not_exceed_initial"),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_factory_flock_status_valid",
        ),
    )
