from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class PoultryType(Base, IDMixin, TimestampMixin):
    __tablename__ = "poultry_types"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="poultry_types")
    feed_types: Mapped[list["FeedType"]] = relationship(
        "FeedType",
        back_populates="poultry_type",
        lazy="selectin",
    )
    slaughter_arrivals: Mapped[list["SlaughterArrival"]] = relationship(
        "SlaughterArrival",
        back_populates="poultry_type",
        lazy="selectin",
    )
    slaughter_semi_products: Mapped[list["SlaughterSemiProduct"]] = relationship(
        "SlaughterSemiProduct",
        back_populates="poultry_type",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", name="uq_poultry_type_org_name"),
        UniqueConstraint("organization_id", "code", name="uq_poultry_type_org_code"),
    )

    @hybrid_property
    def display_name(self) -> str:
        return f"{self.code} - {self.name}"
