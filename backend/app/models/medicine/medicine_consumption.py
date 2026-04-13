from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class MedicineConsumption(Base, IDMixin, TimestampMixin):
    __tablename__ = "medicine_consumptions"

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
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicine_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    consumed_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    purpose: Mapped[str | None] = mapped_column(String(140), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="medicine_consumptions")
    department: Mapped["Department"] = relationship("Department", back_populates="medicine_consumptions")
    batch: Mapped["MedicineBatch"] = relationship("MedicineBatch", back_populates="consumptions")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="medicine_consumptions")
    client: Mapped["Client | None"] = relationship("Client", back_populates="medicine_consumptions")
    created_by_employee: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_medicine_consumption_quantity_positive"),
    )

    @property
    def effective_unit_cost(self) -> Decimal:
        return self.batch.unit_cost if self.batch.unit_cost is not None else Decimal(0)
