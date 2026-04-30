"""Celery tasks модуля matochnik (родительское стадо).

  - daily_log_check_task — 10:00 — напоминание если за сегодня нет ни
    яйцесбора, ни падежа, ни записи о корме у активного стада
  - kpi_alerts_task — 18:00 — алерты по KPI
    (низкая яйценоскость, повышенный падёж за неделю)
"""
from __future__ import annotations

import logging
from datetime import date as _date

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.matochnik.daily_log_check_task")
def daily_log_check_task() -> dict:
    """Проверяет какие активные стада не имеют ни одной записи за сегодня
    (DailyEggProduction / BreedingMortality / BreedingFeedConsumption) и
    шлёт TG-напоминание ответственным с matochnik-доступом.
    """
    from apps.organizations.models import Organization
    from apps.tgbot.tasks import notify_admins_task

    from .models import (
        BreedingFeedConsumption,
        BreedingHerd,
        BreedingMortality,
        DailyEggProduction,
    )

    today = _date.today()
    total_orgs = 0
    total_missing = 0
    notifications_queued = 0

    active_statuses = [
        BreedingHerd.Status.GROWING,
        BreedingHerd.Status.PRODUCING,
    ]

    for org in Organization.objects.filter(is_active=True).iterator():
        total_orgs += 1
        active = list(
            BreedingHerd.objects.filter(
                organization=org,
                status__in=active_statuses,
                placed_at__lte=today,
            ).select_related("block", "technologist")
        )
        if not active:
            continue

        herd_ids = [h.id for h in active]
        eggs_today = set(
            DailyEggProduction.objects
            .filter(herd_id__in=herd_ids, date=today)
            .values_list("herd_id", flat=True)
        )
        mort_today = set(
            BreedingMortality.objects
            .filter(herd_id__in=herd_ids, date=today)
            .values_list("herd_id", flat=True)
        )
        feed_today = set(
            BreedingFeedConsumption.objects
            .filter(herd_id__in=herd_ids, date=today)
            .values_list("herd_id", flat=True)
        )
        reported = eggs_today | mort_today | feed_today

        missing = [h for h in active if h.id not in reported]
        if not missing:
            continue

        total_missing += len(missing)
        text = _format_missing_message(missing, today)
        try:
            notify_admins_task.delay(text, str(org.id), "matochnik")
            notifications_queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("matochnik daily_log_check: failed to enqueue org=%s", org.id)

    payload = {
        "checked_orgs": total_orgs,
        "missing_herds": total_missing,
        "notifications_queued": notifications_queued,
        "on_date": today.isoformat(),
    }
    logger.info("matochnik daily_log_check_task: %s", payload)
    return payload


def _format_missing_message(herds, today: _date) -> str:
    lines = [
        f"⚠️ <b>Маточник · daily-log не заполнен</b> · {today:%d.%m.%Y}",
        "",
        f"Стад без записи на сегодня: <b>{len(herds)}</b>",
        "",
    ]
    for h in herds[:15]:
        block = getattr(h.block, "code", "—") if h.block_id else "—"
        lines.append(
            f"• {h.doc_number} · {block} · {h.current_heads} гол."
        )
    if len(herds) > 15:
        lines.append(f"…и ещё {len(herds) - 15}")
    lines.append("")
    lines.append("Внесите яйцесбор / падёж / расход корма в ERP до 12:00.")
    return "\n".join(lines)


# ─── KPI-алерты ───────────────────────────────────────────────────────────


@shared_task(name="apps.matochnik.kpi_alerts_task")
def kpi_alerts_task() -> dict:
    """Проверяет KPI всех активных стад и шлёт TG-алерт при выходе за пороги
    (низкая яйценоскость / повышенный падёж за неделю).
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
        text = _format_kpi_alerts(alerts)
        try:
            notify_admins_task.delay(text, str(org.id), "matochnik")
            notifications_queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("matochnik kpi_alerts: failed to enqueue org=%s", org.id)

    payload = {
        "checked_orgs": total_orgs,
        "total_alerts": total_alerts,
        "notifications_queued": notifications_queued,
    }
    logger.info("matochnik kpi_alerts_task: %s", payload)
    return payload


def _format_kpi_alerts(alerts: list) -> str:
    lines = ["🚨 <b>KPI-алерты по маточнику</b>", ""]
    for a in alerts[:15]:
        lines.append(
            f"• {a.herd_doc} · {a.block_code} · {a.kind}: <b>{a.value}</b> "
            f"(порог {a.threshold}) · {a.note}",
        )
    if len(alerts) > 15:
        lines.append(f"…и ещё {len(alerts) - 15} алертов")
    lines.append("")
    lines.append("Откройте стадо в ERP для деталей.")
    return "\n".join(lines)
