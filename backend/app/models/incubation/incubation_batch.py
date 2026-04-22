from __future__ import annotations

from datetime import date
from uuid import UUID
from typing import List

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class IncubationBatch(Base, IDMixin, TimestampMixin):
    __tablename__ = "incubation_batches"

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
    batch_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    eggs_arrived: Mapped[int] = mapped_column(Integer, nullable=False)
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    expected_hatch_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="incubation_batches")
    department: Mapped["Department"] = relationship("Department", back_populates="incubation_batches")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")
    runs: Mapped[List["IncubationRun"]] = relationship(
        "IncubationRun",
        back_populates="batch",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "batch_code", name="uq_incubation_batch_org_code"),
        CheckConstraint("eggs_arrived >= 0", name="ck_incubation_batch_eggs_arrived_non_negative"),
    )
