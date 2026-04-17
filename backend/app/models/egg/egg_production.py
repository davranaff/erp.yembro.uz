from __future__ import annotations

from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class EggProduction(Base, IDMixin, TimestampMixin):
    __tablename__ = "egg_production"

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
    produced_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    eggs_collected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eggs_broken: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eggs_rejected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_shelled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eggs_large: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    eggs_medium: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    eggs_small: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    eggs_defective: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="egg_productions")
    department: Mapped["Department"] = relationship("Department", back_populates="egg_productions")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    shipments: Mapped[List["EggShipment"]] = relationship(
        "EggShipment",
        back_populates="production",
        lazy="selectin",
    )
    quality_checks: Mapped[List["EggQualityCheck"]] = relationship(
        "EggQualityCheck",
        back_populates="production",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "department_id", "produced_on", name="uq_egg_prod_org_department_date"),
        CheckConstraint("eggs_collected >= 0", name="ck_egg_prod_eggs_collected_non_negative"),
        CheckConstraint("eggs_broken >= 0", name="ck_egg_prod_eggs_broken_non_negative"),
        CheckConstraint("eggs_rejected >= 0", name="ck_egg_prod_eggs_rejected_non_negative"),
        CheckConstraint("total_shelled >= 0", name="ck_egg_prod_total_shelled_non_negative"),
        CheckConstraint("eggs_large >= 0", name="ck_egg_prod_eggs_large_non_negative"),
        CheckConstraint("eggs_medium >= 0", name="ck_egg_prod_eggs_medium_non_negative"),
        CheckConstraint("eggs_small >= 0", name="ck_egg_prod_eggs_small_non_negative"),
        CheckConstraint("eggs_defective >= 0", name="ck_egg_prod_eggs_defective_non_negative"),
        CheckConstraint(
            "eggs_broken + eggs_rejected <= eggs_collected",
            name="ck_egg_prod_broken_plus_rejected_not_greater_collected",
        ),
        CheckConstraint(
            "total_shelled <= eggs_collected",
            name="ck_egg_prod_total_shelled_not_greater_collected",
        ),
    )

    @hybrid_property
    def net_eggs(self) -> int:
        return max(self.eggs_collected - self.eggs_broken - self.eggs_rejected, 0)
