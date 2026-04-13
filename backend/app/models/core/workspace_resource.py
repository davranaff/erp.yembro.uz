from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class WorkspaceResource(Base, IDMixin, TimestampMixin):
    __tablename__ = "workspace_resources"

    module_key: Mapped[str] = mapped_column(
        ForeignKey("department_modules.key", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_prefix: Mapped[str] = mapped_column(String(96), nullable=False, index=True)
    api_module_key: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=100,
        server_default="100",
        index=True,
    )
    is_head_visible: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    module: Mapped["DepartmentModule"] = relationship(
        "DepartmentModule",
        back_populates="workspace_resources",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("module_key", "key", name="uq_workspace_resource_module_key"),
    )
