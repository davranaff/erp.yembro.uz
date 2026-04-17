from app.repositories.base import BaseRepository
from app.repositories.core import (
    ClientRepository,
    ClientDebtRepository,
    DepartmentRepository,
    OrganizationRepository,
    PoultryTypeRepository,
    WarehouseRepository,
)
from app.repositories.egg import EggMonthlyAnalyticsRepository, EggProductionRepository, EggShipmentRepository
from app.repositories.finance import (
    CashAccountRepository,
    CashTransactionRepository,
    DebtPaymentRepository,
    ExpenseCategoryRepository,
    ExpenseRepository,
    SupplierDebtRepository,
)
from app.repositories.feed import (
    FeedFormulaIngredientRepository,
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedProductionBatchRepository,
    FeedProductShipmentRepository,
    FeedTypeRepository,
)
from app.repositories.hr import EmployeeRepository, PermissionRepository, PositionRepository, RoleRepository
from app.repositories.inventory import StockMovementRepository
from app.repositories.incubation import (
    ChickShipmentRepository,
    FactoryMonthlyAnalyticsRepository,
    IncubationBatchRepository,
    IncubationMonthlyAnalyticsRepository,
    IncubationRunRepository,
)
from app.repositories.medicine import (
    MedicineBatchRepository,
    MedicineTypeRepository,
)
from app.repositories.slaughter import (
    SlaughterMonthlyAnalyticsRepository,
    SlaughterProcessingRepository,
    SlaughterQualityCheckRepository,
    SlaughterSemiProductRepository,
    SlaughterSemiProductShipmentRepository,
)
from app.repositories.system import AuditLogRepository

__all__ = [
    "BaseRepository",
    "OrganizationRepository",
    "DepartmentRepository",
    "WarehouseRepository",
    "ClientRepository",
    "ClientDebtRepository",
    "PoultryTypeRepository",
    "EggProductionRepository",
    "EggShipmentRepository",
    "EggMonthlyAnalyticsRepository",
    "ExpenseCategoryRepository",
    "ExpenseRepository",
    "CashAccountRepository",
    "CashTransactionRepository",
    "SupplierDebtRepository",
    "DebtPaymentRepository",
    "FeedTypeRepository",
    "FeedIngredientRepository",
    "FeedFormulaRepository",
    "FeedFormulaIngredientRepository",
    "FeedProductionBatchRepository",
    "FeedProductShipmentRepository",
    "EmployeeRepository",
    "PositionRepository",
    "RoleRepository",
    "PermissionRepository",
    "StockMovementRepository",
    "ChickShipmentRepository",
    "IncubationBatchRepository",
    "IncubationRunRepository",
    "IncubationMonthlyAnalyticsRepository",
    "FactoryMonthlyAnalyticsRepository",
    "MedicineBatchRepository",
    "MedicineTypeRepository",
    "SlaughterMonthlyAnalyticsRepository",
    "SlaughterProcessingRepository",
    "SlaughterQualityCheckRepository",
    "SlaughterSemiProductRepository",
    "SlaughterSemiProductShipmentRepository",
    "AuditLogRepository",
]
