"""Celery tasks модуля feed."""
from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.feed.apply_feed_shrinkage_task")
def apply_feed_shrinkage_task(on_date: Optional[str] = None) -> dict:
    """Раз в сутки прогоняет алгоритм усушки по всем активным организациям.

    Args:
        on_date: ISO `YYYY-MM-DD`. None = сегодня.

    Returns:
        dict со счётчиками per-org и итогом.
    """
    from apps.organizations.models import Organization

    from .services.shrinkage_runner import apply_for_organization

    target = date.fromisoformat(on_date) if on_date else date.today()

    total_lots = 0
    total_loss_kg = 0.0
    total_movements = 0
    per_org: dict[str, dict] = {}

    for org in Organization.objects.filter(is_active=True).iterator():
        try:
            results = apply_for_organization(org, today=target)
        except Exception:  # noqa: BLE001
            logger.exception("apply_feed_shrinkage_task: org=%s failed", org.id)
            per_org[str(org.id)] = {"error": "exception"}
            continue

        applied = [r for r in results if not r.skipped]
        loss = sum(float(r.loss_kg) for r in applied)
        movs = sum(1 for r in applied if r.movement_id)

        per_org[str(org.id)] = {
            "lots": len(results),
            "applied": len(applied),
            "loss_kg": loss,
            "movements": movs,
        }
        total_lots += len(results)
        total_loss_kg += loss
        total_movements += movs

    payload = {
        "on_date": target.isoformat(),
        "total_lots": total_lots,
        "total_loss_kg": total_loss_kg,
        "total_movements": total_movements,
        "per_org": per_org,
    }
    logger.info("apply_feed_shrinkage_task: %s", payload)
    return payload
