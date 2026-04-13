from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.core import router as core_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.dashboard_overview import router as dashboard_overview_router
from app.api.v1.egg import router as egg_router
from app.api.v1.finance import router as finance_router
from app.api.v1.feed import router as feed_router
from app.api.v1.auth import router as auth_router
from app.api.v1.hr import router as hr_router
from app.api.v1.incubation import router as incubation_router
from app.api.v1.inventory import router as inventory_router
from app.api.v1.medicine import router as medicine_router
from app.api.v1.system import router as system_router
from app.api.v1.slaughter import router as slaughter_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(system_router)
api_router.include_router(dashboard_router)
api_router.include_router(dashboard_overview_router)
api_router.include_router(core_router)
api_router.include_router(egg_router)
api_router.include_router(finance_router)
api_router.include_router(feed_router)
api_router.include_router(hr_router)
api_router.include_router(incubation_router)
api_router.include_router(inventory_router)
api_router.include_router(medicine_router)
api_router.include_router(slaughter_router)
