from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import get_settings
from app.db.pool import Database
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
