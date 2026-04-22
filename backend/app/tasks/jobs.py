from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.pool import Database
from app.repositories.core import CurrencyExchangeRateRepository
from app.services.exchange_rate import CurrencyExchangeRateService
from app.services.telegram_alerts import deliver_operational_admin_alert
from app.taskiq_app import broker


@broker.task(schedule=[{"cron": "*/5 * * * *", "schedule_id": "heartbeat"}])
async def heartbeat_task() -> dict[str, str]:
    return {"beat_at": datetime.now(timezone.utc).isoformat()}


@broker.task(task_name="send_telegram_admin_alert")
async def send_telegram_admin_alert_task(event_payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    db = Database(
        dsn=settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()
    try:
        return await deliver_operational_admin_alert(db, event_payload)
    finally:
        await db.disconnect()


# Sync CBU exchange rates every day at 05:00 UTC = 10:00 Asia/Tashkent.
# CBU publishes next-working-day rates in the evening Tashkent time, so
# by 10:00 the values for "today" are always available.
@broker.task(
    task_name="sync_cbu_exchange_rates",
    schedule=[{"cron": "0 5 * * *", "schedule_id": "sync_cbu_exchange_rates_daily"}],
)
async def sync_cbu_exchange_rates_task() -> dict[str, object]:
    """Periodic job that pulls the latest CBU rates for every organization."""

    settings = get_settings()
    db = Database(
        dsn=settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()
    try:
        service = CurrencyExchangeRateService(CurrencyExchangeRateRepository(db))
        results = await service.sync_all_organizations()
        return {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "organizations": results,
        }
    finally:
        await db.disconnect()
