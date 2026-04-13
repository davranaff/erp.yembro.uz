from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Column, ForeignKey, String, Table, Text, UniqueConstraint, Boolean
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


employee_roles = Table(
    "employee_roles",
    Base.metadata,
    Column("employee_id", PGUUID(as_uuid=True), ForeignKey("employees.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", PGUUID(as_uuid=True), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class Role(Base, IDMixin, TimestampMixin):
    __tablename__ = "roles"

    organization_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    organization: Mapped["Organization"] = relationship("Organization", back_populates="roles")

    employees: Mapped[List["Employee"]] = relationship(
        "Employee",
        secondary="employee_roles",
        back_populates="roles",
        lazy="selectin",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        secondary="role_permissions",
        back_populates="roles",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_roles_org_slug"),
        UniqueConstraint("organization_id", "name", name="uq_roles_org_name"),
    )
