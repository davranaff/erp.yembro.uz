from __future__ import annotations

from app.repositories.base import BaseRepository


class OrganizationRepository(BaseRepository[dict[str, object]]):
    table = "organizations"


class DepartmentModuleRepository(BaseRepository[dict[str, object]]):
    table = "department_modules"


class WorkspaceResourceRepository(BaseRepository[dict[str, object]]):
    table = "workspace_resources"


class DepartmentRepository(BaseRepository[dict[str, object]]):
    table = "departments"


class WarehouseRepository(BaseRepository[dict[str, object]]):
    table = "warehouses"


class ClientRepository(BaseRepository[dict[str, object]]):
    table = "clients"


class ClientDebtRepository(BaseRepository[dict[str, object]]):
    table = "client_debts"


class CurrencyRepository(BaseRepository[dict[str, object]]):
    table = "currencies"


class CurrencyExchangeRateRepository(BaseRepository[dict[str, object]]):
    table = "currency_exchange_rates"


class PoultryTypeRepository(BaseRepository[dict[str, object]]):
    table = "poultry_types"


class MeasurementUnitRepository(BaseRepository[dict[str, object]]):
    table = "measurement_units"


class ClientCategoryRepository(BaseRepository[dict[str, object]]):
    table = "client_categories"


__all__ = [
    "OrganizationRepository",
    "DepartmentModuleRepository",
    "WorkspaceResourceRepository",
    "DepartmentRepository",
    "WarehouseRepository",
    "ClientRepository",
    "ClientDebtRepository",
    "CurrencyRepository",
    "CurrencyExchangeRateRepository",
    "PoultryTypeRepository",
    "MeasurementUnitRepository",
    "ClientCategoryRepository",
]
