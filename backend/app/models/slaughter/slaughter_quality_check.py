from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class SlaughterQualityCheck(Base, IDMixin, TimestampMixin):
    __tablename__ = "slaughter_quality_checks"

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
    semi_product_id: Mapped[UUID] = mapped_column(
        ForeignKey("slaughter_semi_products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    checked_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)
    inspector_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    semi_product: Mapped["SlaughterSemiProduct"] = relationship(
        "SlaughterSemiProduct",
        back_populates="quality_checks",
    )
    inspector: Mapped["Employee | None"] = relationship("Employee", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed')",
            name="ck_slaughter_quality_check_status",
        ),
        CheckConstraint(
            "grade IS NULL OR grade IN ('first', 'second', 'mixed', 'byproduct')",
            name="ck_slaughter_quality_check_grade",
        ),
    )
