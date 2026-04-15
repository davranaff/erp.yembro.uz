from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from taskiq_fastapi import init

from app.api.exceptions import register_exception_handlers
from app.api.middleware import ApiResponseMiddleware
from app.api.router import api_router
from app.core.config import get_settings
from app.core.lifecycle import on_startup, on_shutdown
from app.taskiq_app import broker

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
register_exception_handlers(app)
app.add_middleware(ApiResponseMiddleware)
if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.include_router(api_router)

init(broker, "app.main:app")


@app.on_event("startup")
async def startup_event() -> None:
    await on_startup(app)


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await on_shutdown(app)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
