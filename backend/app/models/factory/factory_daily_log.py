from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional

from ..base import Base, IDMixin, TimestampMixin


class FactoryDailyLog(Base, IDMixin, TimestampMixin):
    """Ежедневный учёт партии на фабрике."""

    __tablename__ = "factory_daily_logs"

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
    log_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    mortality_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sick_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    healthy_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    feed_type_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("feed_types.id", ondelete="SET NULL"),
        nullable=True,
    )
    feed_consumed_kg: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False, default=0)
    feed_cost: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    water_consumed_liters: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    avg_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(5, 1), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="factory_daily_logs")
    department: Mapped["Department"] = relationship("Department", back_populates="factory_daily_logs")
    flock: Mapped["FactoryFlock"] = relationship("FactoryFlock", back_populates="daily_logs")
    feed_type: Mapped["FeedType | None"] = relationship("FeedType")

    __table_args__ = (
        UniqueConstraint("flock_id", "log_date", name="uq_factory_daily_log_flock_date"),
        CheckConstraint("mortality_count >= 0", name="ck_factory_daily_log_mortality_non_negative"),
        CheckConstraint("sick_count >= 0", name="ck_factory_daily_log_sick_non_negative"),
        CheckConstraint("healthy_count >= 0", name="ck_factory_daily_log_healthy_non_negative"),
        CheckConstraint("feed_consumed_kg >= 0", name="ck_factory_daily_log_feed_non_negative"),
        CheckConstraint(
            "water_consumed_liters IS NULL OR water_consumed_liters >= 0",
            name="ck_factory_daily_log_water_non_negative",
        ),
        CheckConstraint(
            "avg_weight_kg IS NULL OR avg_weight_kg >= 0",
            name="ck_factory_daily_log_weight_non_negative",
        ),
        CheckConstraint(
            "temperature IS NULL OR (temperature >= -50 AND temperature <= 80)",
            name="ck_factory_daily_log_temperature_range",
        ),
    )
