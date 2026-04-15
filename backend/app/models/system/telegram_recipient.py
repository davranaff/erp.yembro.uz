from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..base import Base, IDMixin, TimestampMixin


class TelegramRecipient(Base, IDMixin, TimestampMixin):
    __tablename__ = "telegram_recipients"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    telegram_user_id: Mapped[str] = mapped_column(String(80), nullable=False)
    telegram_chat_id: Mapped[str] = mapped_column(String(80), nullable=False)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_language_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    chat_type: Mapped[str] = mapped_column(String(32), nullable=False, default="private", server_default="private")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    last_started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=func.now,
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("telegram_user_id", name="uq_telegram_recipients_telegram_user_id"),
        UniqueConstraint("telegram_chat_id", name="uq_telegram_recipients_telegram_chat_id"),
        Index("ix_telegram_recipients_active_org_user", "organization_id", "user_id", "is_active"),
    )
