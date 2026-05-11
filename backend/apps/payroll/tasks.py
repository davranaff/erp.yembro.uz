"""Celery tasks модуля payroll."""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.payroll.refresh_balance_snapshots")
def refresh_balance_snapshots_task() -> dict:
    """
    Daily refresh всех snapshots балансов ЗП. Запускается celery beat'ом
    раз в сутки (см. CELERY_BEAT_SCHEDULE в settings).

    Returns:
        dict с per-organization counters и общим totals.
    """
    from apps.organizations.models import Organization

    from .services.snapshot import refresh_balance_snapshots

    per_org: dict[str, int] = {}
    total = 0
    for org in Organization.objects.filter(is_active=True):
        n = refresh_balance_snapshots(organization=org)
        per_org[org.code] = n
        total += n
    logger.info("payroll snapshots refreshed: total=%d, per_org=%s", total, per_org)
    return {"total": total, "per_org": per_org}
