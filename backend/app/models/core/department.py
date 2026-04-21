from __future__ import annotations

from typing import List
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Department(Base, IDMixin, TimestampMixin):
    __tablename__ = "departments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    code: Mapped[str | None] = mapped_column(String(60), nullable=True, index=True)
    module_key: Mapped[str] = mapped_column(
        ForeignKey("department_modules.key", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    icon: Mapped[str | None] = mapped_column(String(48), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    parent_department_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    head_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("employees.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    organization: Mapped["Organization"] = relationship("Organization", back_populates="departments")
    department_module: Mapped["DepartmentModule"] = relationship(
        "DepartmentModule",
        back_populates="departments",
        lazy="selectin",
    )
    parent_department: Mapped["Department | None"] = relationship(
        "Department",
        remote_side="Department.id",
        back_populates="child_departments",
    )
    child_departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="parent_department",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    head: Mapped["Employee | None"] = relationship(
        "Employee",
        back_populates="headed_departments",
        lazy="selectin",
    )
    employees: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="department",
        lazy="selectin",
    )
    positions: Mapped[List["Position"]] = relationship(
        "Position",
        back_populates="department",
        lazy="selectin",
    )
    egg_productions: Mapped[List["EggProduction"]] = relationship(
        "EggProduction",
        back_populates="department",
        lazy="selectin",
    )
    egg_shipments: Mapped[List["EggShipment"]] = relationship(
        "EggShipment",
        back_populates="department",
        lazy="selectin",
    )
    egg_monthly_analytics: Mapped[List["EggMonthlyAnalytics"]] = relationship(
        "EggMonthlyAnalytics",
        back_populates="department",
        lazy="selectin",
    )
    expenses: Mapped[List["Expense"]] = relationship(
        "Expense",
        back_populates="department",
        lazy="selectin",
    )
    expense_categories: Mapped[List["ExpenseCategory"]] = relationship(
        "ExpenseCategory",
        back_populates="department",
        lazy="selectin",
    )
    cash_accounts: Mapped[List["CashAccount"]] = relationship(
        "CashAccount",
        back_populates="department",
        lazy="selectin",
    )
    warehouses: Mapped[List["Warehouse"]] = relationship(
        "Warehouse",
        back_populates="department",
        lazy="selectin",
    )
    feed_production_batches: Mapped[List["FeedProductionBatch"]] = relationship(
        "FeedProductionBatch",
        back_populates="department",
        lazy="selectin",
    )
    feed_product_shipments: Mapped[List["FeedProductShipment"]] = relationship(
        "FeedProductShipment",
        back_populates="department",
        lazy="selectin",
    )
    slaughter_arrivals: Mapped[List["SlaughterArrival"]] = relationship(
        "SlaughterArrival",
        back_populates="department",
        lazy="selectin",
    )
    slaughter_processings: Mapped[List["SlaughterProcessing"]] = relationship(
        "SlaughterProcessing",
        back_populates="department",
        lazy="selectin",
    )
    slaughter_semi_products: Mapped[List["SlaughterSemiProduct"]] = relationship(
        "SlaughterSemiProduct",
        back_populates="department",
        lazy="selectin",
    )
    slaughter_semi_product_shipments: Mapped[List["SlaughterSemiProductShipment"]] = relationship(
        "SlaughterSemiProductShipment",
        back_populates="department",
        lazy="selectin",
    )
    slaughter_monthly_analytics: Mapped[List["SlaughterMonthlyAnalytics"]] = relationship(
        "SlaughterMonthlyAnalytics",
        back_populates="department",
        lazy="selectin",
    )
    medicine_batches: Mapped[List["MedicineBatch"]] = relationship(
        "MedicineBatch",
        back_populates="department",
        lazy="selectin",
    )
    factory_monthly_analytics: Mapped[List["FactoryMonthlyAnalytics"]] = relationship(
        "FactoryMonthlyAnalytics",
        back_populates="department",
        lazy="selectin",
    )
    incubation_batches: Mapped[List["IncubationBatch"]] = relationship(
        "IncubationBatch",
        back_populates="department",
        lazy="selectin",
    )
    incubation_runs: Mapped[List["IncubationRun"]] = relationship(
        "IncubationRun",
        back_populates="department",
        lazy="selectin",
    )
    chick_shipments: Mapped[List["ChickShipment"]] = relationship(
        "ChickShipment",
        back_populates="department",
        lazy="selectin",
    )
    incubation_monthly_analytics: Mapped[List["IncubationMonthlyAnalytics"]] = relationship(
        "IncubationMonthlyAnalytics",
        back_populates="department",
        lazy="selectin",
    )
    factory_flocks: Mapped[List["FactoryFlock"]] = relationship(
        "FactoryFlock",
        back_populates="department",
        lazy="selectin",
    )
    factory_daily_logs: Mapped[List["FactoryDailyLog"]] = relationship(
        "FactoryDailyLog",
        back_populates="department",
        lazy="selectin",
    )
    factory_shipments: Mapped[List["FactoryShipment"]] = relationship(
        "FactoryShipment",
        back_populates="department",
        lazy="selectin",
    )
    factory_medicine_usages: Mapped[List["FactoryMedicineUsage"]] = relationship(
        "FactoryMedicineUsage",
        back_populates="department",
        lazy="selectin",
    )
    factory_vaccination_plans: Mapped[List["FactoryVaccinationPlan"]] = relationship(
        "FactoryVaccinationPlan",
        back_populates="department",
        lazy="selectin",
    )
    clients: Mapped[List["Client"]] = relationship(
        "Client",
        back_populates="department",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "module_key", "name", name="uq_department_org_module_name"),
        UniqueConstraint("organization_id", "module_key", "code", name="uq_department_org_module_code"),
    )
