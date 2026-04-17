from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class MedicineBatch(Base, IDMixin, TimestampMixin):
    __tablename__ = "medicine_batches"

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
    medicine_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicine_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    supplier_client_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("clients.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    batch_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    arrived_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    received_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    remaining_quantity: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs", server_default="pcs")
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_public_token: Mapped[str | None] = mapped_column(Text, nullable=True, index=True)
    qr_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qr_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    qr_image_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    qr_image_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    qr_image_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    attachment_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    attachment_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="medicine_batches")
    department: Mapped["Department"] = relationship("Department", back_populates="medicine_batches")
    medicine_type: Mapped["MedicineType"] = relationship("MedicineType", back_populates="medicine_batches")
    supplier_client: Mapped["Client | None"] = relationship("Client", back_populates="medicine_batches")
    warehouse: Mapped["Warehouse | None"] = relationship("Warehouse")

    __table_args__ = (
        UniqueConstraint("organization_id", "batch_code", name="uq_medicine_batch_org_code"),
        UniqueConstraint("organization_id", "barcode", name="uq_medicine_batch_org_barcode"),
        CheckConstraint("received_quantity >= 0", name="ck_medicine_batch_received_non_negative"),
        CheckConstraint("remaining_quantity >= 0", name="ck_medicine_batch_remaining_non_negative"),
        CheckConstraint("received_quantity >= remaining_quantity", name="ck_medicine_batch_remaining_not_exceed_received"),
        CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_medicine_batch_unit_cost_non_negative"),
        CheckConstraint(
            "expiry_date IS NULL OR expiry_date >= arrived_on",
            name="ck_medicine_batch_expiry_after_arrival",
        ),
    )

    @hybrid_property
    def consumed_quantity(self) -> Decimal:
        return self.received_quantity - self.remaining_quantity

    @hybrid_property
    def stocked_value(self) -> Decimal:
        if self.unit_cost is None:
            return Decimal(0)
        return self.remaining_quantity * self.unit_cost
