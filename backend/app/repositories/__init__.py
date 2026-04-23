from app.repositories.base import BaseRepository
from app.repositories.core import (
    ClientRepository,
    ClientDebtRepository,
    DepartmentRepository,
    OrganizationRepository,
    PoultryTypeRepository,
    WarehouseRepository,
)
from app.repositories.egg import EggProductionRepository, EggShipmentRepository
from app.repositories.finance import (
    CashAccountRepository,
    CashTransactionRepository,
    DebtPaymentRepository,
    ExpenseCategoryRepository,
    SupplierDebtRepository,
)
from app.repositories.feed import (
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
    IncubationBatchRepository,
    IncubationRunRepository,
)
from app.repositories.medicine import (
    MedicineBatchRepository,
    MedicineTypeRepository,
)
from app.repositories.slaughter import (
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
    "ExpenseCategoryRepository",
    "CashAccountRepository",
    "CashTransactionRepository",
    "SupplierDebtRepository",
    "DebtPaymentRepository",
    "FeedTypeRepository",
    "FeedIngredientRepository",
    "FeedFormulaRepository",
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
    "MedicineBatchRepository",
    "MedicineTypeRepository",
    "SlaughterProcessingRepository",
    "SlaughterQualityCheckRepository",
    "SlaughterSemiProductRepository",
    "SlaughterSemiProductShipmentRepository",
    "AuditLogRepository",
]
