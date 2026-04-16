from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class MeasurementUnit(Base, IDMixin, TimestampMixin):
    __tablename__ = "measurement_units"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="measurement_units")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_measurement_unit_org_code"),
        UniqueConstraint("organization_id", "name", name="uq_measurement_unit_org_name"),
    )
