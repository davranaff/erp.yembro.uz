from __future__ import annotations

from decimal import Decimal
from typing import List
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Position(Base, IDMixin, TimestampMixin):
    __tablename__ = "positions"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(140), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="positions")
    department: Mapped["Department | None"] = relationship(
        "Department",
        back_populates="positions",
    )
    employees: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="position",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_position_org_slug"),
        UniqueConstraint("organization_id", "title", name="uq_position_org_title"),
        CheckConstraint("min_salary IS NULL OR min_salary >= 0", name="ck_position_min_salary_non_negative"),
        CheckConstraint("max_salary IS NULL OR max_salary >= 0", name="ck_position_max_salary_non_negative"),
        CheckConstraint(
            "min_salary IS NULL OR max_salary IS NULL OR min_salary <= max_salary",
            name="ck_position_salary_range",
        ),
    )
