from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Currency(Base, IDMixin, TimestampMixin):
    __tablename__ = "currencies"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    symbol: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    exchange_rate_to_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 6), nullable=False, default=Decimal("1.0"), server_default="1.0"
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="currencies")

    __table_args__ = (
        UniqueConstraint("organization_id", "code", name="uq_currency_org_code"),
        UniqueConstraint("organization_id", "name", name="uq_currency_org_name"),
    )
