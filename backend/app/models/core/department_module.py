from __future__ import annotations

from typing import List

from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class DepartmentModule(Base, IDMixin, TimestampMixin):
    __tablename__ = "department_modules"

    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(48), nullable=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
        index=True,
    )
    is_department_assignable: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    analytics_section_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    implicit_read_permissions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )
    analytics_read_permissions: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default="[]",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="department_module",
        lazy="selectin",
    )
    workspace_resources: Mapped[List["WorkspaceResource"]] = relationship(
        "WorkspaceResource",
        back_populates="module",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("key", name="uq_department_module_key"),
    )
