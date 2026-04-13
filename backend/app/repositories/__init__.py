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
from app.repositories.finance import ExpenseCategoryRepository, ExpenseRepository
from app.repositories.feed import (
    FeedArrivalRepository,
    FeedFormulaIngredientRepository,
    FeedFormulaRepository,
    FeedIngredientRepository,
    FeedProductionBatchRepository,
    FeedProductShipmentRepository,
    FeedRawArrivalRepository,
    FeedRawConsumptionRepository,
    FeedTypeRepository,
)
from app.repositories.hr import EmployeeRepository, PermissionRepository, PositionRepository, RoleRepository
from app.repositories.inventory import StockMovementRepository
from app.repositories.incubation import (
    ChickArrivalRepository,
    ChickShipmentRepository,
    FactoryMonthlyAnalyticsRepository,
    IncubationBatchRepository,
    IncubationMonthlyAnalyticsRepository,
    IncubationRunRepository,
)
from app.repositories.medicine import (
    MedicineArrivalRepository,
    MedicineBatchRepository,
    MedicineConsumptionRepository,
    MedicineTypeRepository,
)
from app.repositories.slaughter import (
    SlaughterArrivalRepository,
    SlaughterProcessingRepository,
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
    "FeedTypeRepository",
    "FeedIngredientRepository",
    "FeedArrivalRepository",
    "FeedFormulaRepository",
    "FeedFormulaIngredientRepository",
    "FeedRawArrivalRepository",
    "FeedProductionBatchRepository",
    "FeedRawConsumptionRepository",
    "FeedProductShipmentRepository",
    "EmployeeRepository",
    "PositionRepository",
    "RoleRepository",
    "PermissionRepository",
    "StockMovementRepository",
    "ChickArrivalRepository",
    "ChickShipmentRepository",
    "IncubationBatchRepository",
    "IncubationRunRepository",
    "IncubationMonthlyAnalyticsRepository",
    "FactoryMonthlyAnalyticsRepository",
    "MedicineArrivalRepository",
    "MedicineBatchRepository",
    "MedicineConsumptionRepository",
    "MedicineTypeRepository",
    "SlaughterArrivalRepository",
    "SlaughterProcessingRepository",
    "SlaughterSemiProductRepository",
    "SlaughterSemiProductShipmentRepository",
    "AuditLogRepository",
]
