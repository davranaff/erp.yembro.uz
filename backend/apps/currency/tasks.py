"""
Celery tasks for currency sync.
"""
import logging
from datetime import date
from typing import Optional

from celery import shared_task

from .services.cbu import CBUFetchError, sync_cbu_rates


logger = logging.getLogger(__name__)


def _log_sync(*, status: str, stats: Optional[dict] = None,
              error_message: str = "", triggered_by: str = "beat") -> None:
    """Записать факт sync в IntegrationSyncLog. Никогда не падает."""
    try:
        from .models import IntegrationSyncLog
        IntegrationSyncLog.objects.create(
            provider="cbu.uz",
            status=status,
            stats=stats,
            error_message=error_message[:500] if error_message else "",
            triggered_by=triggered_by,
        )
    except Exception:  # noqa: BLE001
        logger.exception("Не удалось записать IntegrationSyncLog")


@shared_task(
    bind=True,
    autoretry_for=(CBUFetchError,),
    retry_backoff=True,
    retry_backoff_max=3600,
    max_retries=5,
    name="apps.currency.sync_cbu_rates_task",
)
def sync_cbu_rates_task(self, on_date: Optional[str] = None) -> dict:
    """
    Синхронизировать курсы cbu.uz → ExchangeRate.

    Args:
        on_date: ISO date string "YYYY-MM-DD", или None для сегодняшнего.

    Returns:
        dict со счётчиками (fetched, created, updated, skipped, currencies_created).
    """
    target_date: Optional[date] = None
    if on_date:
        target_date = date.fromisoformat(on_date)

    logger.info("CBU sync started (on_date=%s, attempt=%s)",
                target_date, self.request.retries + 1)
    try:
        result = sync_cbu_rates(on_date=target_date)
    except CBUFetchError as exc:
        # Финальная неудача (после исчерпания всех retry) запишется через
        # on_failure ниже. Здесь лишь логируем — autoretry заберёт исключение.
        logger.warning("CBU sync attempt failed: %s", exc)
        raise

    payload = result.as_dict()
    logger.info("CBU sync finished: %s", payload)
    _log_sync(status="success", stats=payload, triggered_by="beat")
    return payload


# Перехватчик финального failure (после max_retries) — пишет в IntegrationSyncLog,
# чтобы админ увидел в /api/currency/sync-log/, что курсы «застряли».
def _on_sync_failure(self, exc, task_id, args, kwargs, einfo):
    _log_sync(
        status="failed",
        error_message=f"{type(exc).__name__}: {exc}",
        triggered_by="beat",
    )


sync_cbu_rates_task.on_failure = _on_sync_failure  # type: ignore[assignment]
