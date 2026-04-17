from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class MedicineType(Base, IDMixin, TimestampMixin):
    __tablename__ = "medicine_types"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="medicine_types")
    medicine_batches: Mapped[List["MedicineBatch"]] = relationship(
        "MedicineBatch",
        back_populates="medicine_type",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_medicine_type_org_code"),
    )
