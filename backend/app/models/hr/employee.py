from __future__ import annotations

from datetime import time
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from ..base import Base, IDMixin, TimestampMixin
from app.utils.password import hash_password, is_hashed_password, verify_password


class Employee(Base, IDMixin, TimestampMixin):
    __tablename__ = "employees"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    work_start_time: Mapped[Optional[time]] = mapped_column(nullable=True)
    work_end_time: Mapped[Optional[time]] = mapped_column(nullable=True)
    department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    position_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("positions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    phone: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    organization: Mapped["Organization"] = relationship("Organization", back_populates="employees")
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="employees", lazy="selectin")
    position: Mapped[Optional["Position"]] = relationship("Position", back_populates="employees", lazy="selectin")
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="employee_roles",
        back_populates="employees",
        lazy="selectin",
    )
    headed_departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="head",
        lazy="selectin",
    )

    __table_args__ = (
        Index("uq_employee_org_email", "organization_id", "email", unique=True),
        Index("uq_employee_org_key", "organization_id", "organization_key", unique=True),
        Index("ix_employee_org_key", "organization_key"),
        Index("ix_employee_department", "department_id"),
        Index("ix_employee_position", "position_id"),
        CheckConstraint("salary IS NULL OR salary >= 0", name="ck_employee_salary_non_negative"),
        CheckConstraint(
            "(work_start_time IS NULL) OR (work_end_time IS NULL) OR (work_start_time < work_end_time)",
            name="ck_employee_work_time_order",
        ),
    )

    def permission_codes(self) -> set[str]:
        permissions: set[str] = set()
        for role in self.roles:
            if not role.is_active:
                continue
            for permission in role.permissions:
                if permission.is_active:
                    permissions.add(permission.code)
        return permissions

    def has_permission(self, permission_code: str) -> bool:
        return permission_code in self.permission_codes()

    def set_password(self, password: str) -> None:
        self.password = hash_password(password)

    def verify_password(self, password: str) -> bool:
        return verify_password(password, self.password)

    @validates("password")
    def _validate_password(self, key: str, value: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError("Password is required")
        if is_hashed_password(value):
            return value
        return hash_password(value)
