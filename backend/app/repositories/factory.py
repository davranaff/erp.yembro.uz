from app.repositories.base import BaseRepository


class FactoryFlockRepository(BaseRepository[dict[str, object]]):
    table = "factory_flocks"


class FactoryDailyLogRepository(BaseRepository[dict[str, object]]):
    table = "factory_daily_logs"


class FactoryShipmentRepository(BaseRepository[dict[str, object]]):
    table = "factory_shipments"


class FactoryMedicineUsageRepository(BaseRepository[dict[str, object]]):
    table = "factory_medicine_usages"



class FactoryVaccinationPlanRepository(BaseRepository[dict[str, object]]):
    table = "factory_vaccination_plans"
