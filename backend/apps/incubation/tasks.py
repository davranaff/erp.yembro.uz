"""Celery tasks модуля incubation.

  - kpi_alerts_task — алерты по hatch rate за последние 24 часа.
"""
from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.incubation.kpi_alerts_task")
def kpi_alerts_task() -> dict:
    """Проверяет hatch rate всех партий, закрытых за последние 24ч, и шлёт
    TG-алерт если ниже порога `INCUBATION_HATCH_RATE_ALERT_PCT`.

    Расписание: ежедневно 19:00 Asia/Tashkent (после feedlot KPI 18:00).
    """
    from apps.organizations.models import Organization
    from apps.tgbot.tasks import notify_admins_task

    from .services.kpi_alerts import collect_org_alerts

    total_orgs = 0
    total_alerts = 0
    notifications_queued = 0

    for org in Organization.objects.filter(is_active=True).iterator():
        total_orgs += 1
        alerts = collect_org_alerts(org)
        if not alerts:
            continue
        total_alerts += len(alerts)

        text = _format_alerts(alerts)
        try:
            notify_admins_task.delay(text, str(org.id), "incubation")
            notifications_queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("incubation kpi_alerts_task: failed for org=%s", org.id)

    payload = {
        "checked_orgs": total_orgs,
        "total_alerts": total_alerts,
        "notifications_queued": notifications_queued,
    }
    logger.info("incubation.kpi_alerts_task: %s", payload)
    return payload


def _format_alerts(alerts: list) -> str:
    lines = ["🥚 <b>Инкубация: низкий hatch rate</b>", ""]
    for a in alerts[:15]:
        lines.append(
            f"• {a.run_doc}: <b>{a.hatch_rate_pct}%</b> "
            f"(норма ≥ {a.threshold_pct}%) · "
            f"{a.hatched}/{a.fertile} вывелось",
        )
    if len(alerts) > 15:
        lines.append(f"…и ещё {len(alerts) - 15} партий")
    lines.append("")
    lines.append("Откройте партию инкубации в ERP для деталей.")
    return "\n".join(lines)
