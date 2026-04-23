from __future__ import annotations

from typing import List

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..base import Base, IDMixin, TimestampMixin


class Organization(Base, IDMixin, TimestampMixin):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")

    employees: Mapped[List["Employee"]] = relationship(
        "Employee",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    clients: Mapped[List["Client"]] = relationship(
        "Client",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    departments: Mapped[List["Department"]] = relationship(
        "Department",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    warehouses: Mapped[List["Warehouse"]] = relationship(
        "Warehouse",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    positions: Mapped[List["Position"]] = relationship(
        "Position",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    expense_categories: Mapped[List["ExpenseCategory"]] = relationship(
        "ExpenseCategory",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cash_accounts: Mapped[List["CashAccount"]] = relationship(
        "CashAccount",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    cash_transactions: Mapped[List["CashTransaction"]] = relationship(
        "CashTransaction",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    egg_productions: Mapped[List["EggProduction"]] = relationship(
        "EggProduction",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    egg_shipments: Mapped[List["EggShipment"]] = relationship(
        "EggShipment",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incubation_batches: Mapped[List["IncubationBatch"]] = relationship(
        "IncubationBatch",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incubation_runs: Mapped[List["IncubationRun"]] = relationship(
        "IncubationRun",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    chick_shipments: Mapped[List["ChickShipment"]] = relationship(
        "ChickShipment",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    poultry_types: Mapped[List["PoultryType"]] = relationship(
        "PoultryType",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    currencies: Mapped[List["Currency"]] = relationship(
        "Currency",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    measurement_units: Mapped[List["MeasurementUnit"]] = relationship(
        "MeasurementUnit",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    client_categories: Mapped[List["ClientCategory"]] = relationship(
        "ClientCategory",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feed_types: Mapped[List["FeedType"]] = relationship(
        "FeedType",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feed_ingredients: Mapped[List["FeedIngredient"]] = relationship(
        "FeedIngredient",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feed_formulas: Mapped[List["FeedFormula"]] = relationship(
        "FeedFormula",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    medicine_types: Mapped[List["MedicineType"]] = relationship(
        "MedicineType",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slaughter_arrivals: Mapped[List["SlaughterArrival"]] = relationship(
        "SlaughterArrival",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slaughter_processings: Mapped[List["SlaughterProcessing"]] = relationship(
        "SlaughterProcessing",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slaughter_semi_products: Mapped[List["SlaughterSemiProduct"]] = relationship(
        "SlaughterSemiProduct",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    slaughter_semi_product_shipments: Mapped[List["SlaughterSemiProductShipment"]] = relationship(
        "SlaughterSemiProductShipment",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    medicine_batches: Mapped[List["MedicineBatch"]] = relationship(
        "MedicineBatch",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feed_production_batches: Mapped[List["FeedProductionBatch"]] = relationship(
        "FeedProductionBatch",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    feed_product_shipments: Mapped[List["FeedProductShipment"]] = relationship(
        "FeedProductShipment",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    factory_medicine_usages: Mapped[List["FactoryMedicineUsage"]] = relationship(
        "FactoryMedicineUsage",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    factory_vaccination_plans: Mapped[List["FactoryVaccinationPlan"]] = relationship(
        "FactoryVaccinationPlan",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    factory_flocks: Mapped[List["FactoryFlock"]] = relationship(
        "FactoryFlock",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    factory_daily_logs: Mapped[List["FactoryDailyLog"]] = relationship(
        "FactoryDailyLog",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    factory_shipments: Mapped[List["FactoryShipment"]] = relationship(
        "FactoryShipment",
        back_populates="organization",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
