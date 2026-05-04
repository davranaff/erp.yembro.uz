"""
Celery-задачи модуля вет.аптеки.

Запланированы Celery beat (см. миграцию 0003_seed_vet_status_beat).
"""
import logging

from celery import shared_task

from .services.auto_status import auto_update_vet_stock_status


logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    name="apps.vet.auto_update_stock_status",
    max_retries=3,
)
def auto_update_stock_status_task(self) -> dict:
    """
    Авто-перевод статусов лотов по сроку годности.

    Returns:
        dict со счётчиками: {"expired": N, "expiring": M}.
    """
    logger.info("vet.auto_update_stock_status started")
    result = auto_update_vet_stock_status()
    payload = result.as_dict()
    logger.info("vet.auto_update_stock_status finished: %s", payload)
    return payload
