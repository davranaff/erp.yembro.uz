from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..base import Base, IDMixin


class AuditLog(Base, IDMixin):
    __tablename__ = "audit_logs"

    organization_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_table: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(140), nullable=True, index=True)
    actor_roles: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    changed_fields: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    before_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    context_data: Mapped[dict[str, object] | None] = mapped_column(JSON, nullable=True)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now,
        server_default=func.now(),
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('create', 'update', 'delete')",
            name="ck_audit_logs_action_allowed",
        ),
        Index(
            "ix_audit_logs_entity_lookup",
            "organization_id",
            "entity_table",
            "entity_id",
            "changed_at",
        ),
    )
