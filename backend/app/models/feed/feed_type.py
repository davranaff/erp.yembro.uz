from __future__ import annotations

from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class FeedType(Base, IDMixin, TimestampMixin):
    __tablename__ = "feed_types"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    poultry_type_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("poultry_types.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg", server_default="kg")
    measurement_unit_id: Mapped[UUID] = mapped_column(
        ForeignKey("measurement_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="feed_types")
    poultry_type: Mapped["PoultryType | None"] = relationship("PoultryType", back_populates="feed_types")
    formulas: Mapped[list["FeedFormula"]] = relationship(
        "FeedFormula",
        back_populates="feed_type",
        lazy="selectin",
    )
    shipments: Mapped[list["FeedProductShipment"]] = relationship(
        "FeedProductShipment",
        back_populates="feed_type",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_feed_type_org_code"),
    )
