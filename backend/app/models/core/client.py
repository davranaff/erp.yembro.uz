from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Client(Base, IDMixin, TimestampMixin):
    __tablename__ = "clients"

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
    first_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    client_code: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="clients")
    department: Mapped["Department | None"] = relationship("Department", back_populates="clients")
    egg_shipments: Mapped[list["EggShipment"]] = relationship(
        "EggShipment",
        back_populates="client",
        lazy="selectin",
    )

    __table_args__ = (
        Index("uq_client_org_email", "organization_id", "email", unique=True),
        Index("uq_client_org_code", "organization_id", "client_code", unique=True),
    )

    feed_product_shipments: Mapped[List["FeedProductShipment"]] = relationship(
        "FeedProductShipment",
        back_populates="client",
        lazy="selectin",
    )
    medicine_batches: Mapped[List["MedicineBatch"]] = relationship(
        "MedicineBatch",
        back_populates="supplier_client",
        lazy="selectin",
    )
    slaughter_semi_product_shipments: Mapped[List["SlaughterSemiProductShipment"]] = relationship(
        "SlaughterSemiProductShipment",
        back_populates="client",
        lazy="selectin",
    )

    chick_shipments: Mapped[List["ChickShipment"]] = relationship(
        "ChickShipment",
        back_populates="client",
        lazy="selectin",
    )
    factory_source_flocks: Mapped[List["FactoryFlock"]] = relationship(
        "FactoryFlock",
        back_populates="source_client",
        lazy="selectin",
    )
    factory_shipments: Mapped[List["FactoryShipment"]] = relationship(
        "FactoryShipment",
        back_populates="client",
        lazy="selectin",
    )
