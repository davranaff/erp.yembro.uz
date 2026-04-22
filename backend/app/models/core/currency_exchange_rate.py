from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class CurrencyExchangeRate(Base, IDMixin, TimestampMixin):
    """History of exchange rates for a given currency on a given date.

    ``rate`` is ``exchange_rate_to_base`` — how many base-currency units
    you get for one unit of this currency on that date. For the base
    currency itself the rate is always ``1``.

    Source is usually ``"cbu"`` (synced from cbu.uz) but may also be
    ``"manual"`` when the admin enters a custom rate.
    """

    __tablename__ = "currency_exchange_rates"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    currency_id: Mapped[UUID] = mapped_column(
        ForeignKey("currencies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rate_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="cbu", server_default="cbu", index=True
    )
    source_ref: Mapped[str | None] = mapped_column(String(120), nullable=True)

    organization: Mapped["Organization"] = relationship(  # noqa: F821
        "Organization", lazy="selectin"
    )
    currency: Mapped["Currency"] = relationship(  # noqa: F821
        "Currency", lazy="selectin"
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "currency_id",
            "rate_date",
            name="uq_currency_rate_org_currency_date",
        ),
        Index(
            "ix_currency_rate_org_currency_date",
            "organization_id",
            "currency_id",
            "rate_date",
        ),
        CheckConstraint("rate > 0", name="ck_currency_rate_positive"),
    )
