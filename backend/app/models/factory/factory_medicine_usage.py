from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FactoryMedicineUsage(Base, IDMixin, TimestampMixin):
    """Расход лекарств по партии на фабрике."""

    __tablename__ = "factory_medicine_usages"

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
    usage_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    medicine_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicine_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    medicine_batch_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("medicine_batches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    total_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    measurement_unit_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_medicine_usages")
    department: Mapped["Department"] = relationship("Department", back_populates="factory_medicine_usages")
    flock: Mapped["FactoryFlock"] = relationship("FactoryFlock", back_populates="medicine_usages")
    medicine_type: Mapped["MedicineType"] = relationship("MedicineType")
    medicine_batch: Mapped["MedicineBatch | None"] = relationship("MedicineBatch")
    measurement_unit: Mapped["MeasurementUnit | None"] = relationship("MeasurementUnit")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_factory_medicine_usage_quantity_positive"),
    )
