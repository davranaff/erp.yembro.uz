"""Celery tasks модуля feedlot.

Реализует Этап 1 ТЗ:
  - F1.1: Telegram-пуш если daily-log не заполнен к 10:00
  - F1.x: KPI-алерты (см. отдельный модуль services/kpi_alerts.py)
"""
from __future__ import annotations

import logging
from datetime import date as _date

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.feedlot.daily_log_check_task")
def daily_log_check_task() -> dict:
    """Проверяет какие активные партии откорма не имеют записи daily-log за
    сегодня, и отправляет Telegram-уведомление технологам/админам с feedlot-доступом.

    Daily-log = либо `DailyWeighing`, либо `FeedlotMortality` за сегодня.
    Если ни того, ни другого нет — партия считается «не отчитавшейся».

    Расписание: ежедневно 10:00 Asia/Tashkent (см. миграцию
    `feedlot/0002_seed_daily_log_check_beat.py`). Согласно ТЗ — критерий
    приёмки UAT «≥ 80% daily-log заполнено к 12:00», поэтому в 10:00 даём
    мягкое напоминание оставшимся.
    """
    from apps.organizations.models import Organization
    from apps.tgbot.tasks import notify_admins_task

    from .models import DailyWeighing, FeedlotBatch, FeedlotMortality

    today = _date.today()
    total_orgs = 0
    total_missing = 0
    notifications_queued = 0

    active_statuses = [
        FeedlotBatch.Status.PLACED,
        FeedlotBatch.Status.GROWING,
        FeedlotBatch.Status.READY_SLAUGHTER,
    ]

    for org in Organization.objects.filter(is_active=True).iterator():
        total_orgs += 1
        active = list(
            FeedlotBatch.objects.filter(
                organization=org,
                status__in=active_statuses,
                placed_date__lte=today,  # партия должна быть посажена не позже сегодня
            ).select_related("house_block", "technologist")
        )
        if not active:
            continue

        # За один запрос — какие batch_id уже имеют запись за сегодня
        weighed_today = set(
            DailyWeighing.objects.filter(
                feedlot_batch__in=active, date=today,
            ).values_list("feedlot_batch_id", flat=True)
        )
        mortality_today = set(
            FeedlotMortality.objects.filter(
                feedlot_batch__in=active, date=today,
            ).values_list("feedlot_batch_id", flat=True)
        )
        reported = weighed_today | mortality_today

        missing = [b for b in active if b.id not in reported]
        if not missing:
            continue

        total_missing += len(missing)
        text = _format_missing_message(missing, today)
        try:
            notify_admins_task.delay(
                text, str(org.id), "feedlot",
            )
            notifications_queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("daily_log_check_task: failed to enqueue notify org=%s", org.id)

    payload = {
        "checked_orgs": total_orgs,
        "missing_batches": total_missing,
        "notifications_queued": notifications_queued,
        "on_date": today.isoformat(),
    }
    logger.info("daily_log_check_task: %s", payload)
    return payload


def _format_missing_message(batches, today: _date) -> str:
    """Формирует текст уведомления (HTML для Telegram)."""
    lines = [
        f"⚠️ <b>Daily-log не заполнен</b> · {today:%d.%m.%Y}",
        "",
        f"Партий без записи на сегодня: <b>{len(batches)}</b>",
        "",
    ]
    for b in batches[:15]:  # больше 15 в одно сообщение TG не вмещает приятно
        house = getattr(b.house_block, "code", "—")
        days = (today - b.placed_date).days if b.placed_date else 0
        lines.append(
            f"• {b.doc_number} · {house} · день {days} · {b.current_heads} гол."
        )
    if len(batches) > 15:
        lines.append(f"…и ещё {len(batches) - 15}")
    lines.append("")
    lines.append("Заполните взвешивание/падёж в ERP до 12:00.")
    return "\n".join(lines)


# ─── KPI-алерты ───────────────────────────────────────────────────────────


@shared_task(name="apps.feedlot.kpi_alerts_task")
def kpi_alerts_task() -> dict:
    """Проверяет KPI всех активных партий откорма и шлёт алерты при
    выходе за пороги (mortality, FCR).

    Пороги из settings:
      FEEDLOT_MORTALITY_ALERT_PCT — выше этого % падежа от initial → алерт
      FEEDLOT_FCR_ALERT_VALUE     — выше этого FCR → алерт
      FEEDLOT_FCR_ALERT_MIN_DAY   — не алертим до этого дня (FCR на ранних днях шумный)

    Расписание: ежедневно 18:00 Asia/Tashkent — вечерний разбор полётов,
    к этому времени все daily-log должны быть в системе.
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
            notify_admins_task.delay(text, str(org.id), "feedlot")
            notifications_queued += 1
        except Exception:  # noqa: BLE001
            logger.exception("kpi_alerts_task: failed to enqueue notify org=%s", org.id)

    payload = {
        "checked_orgs": total_orgs,
        "total_alerts": total_alerts,
        "notifications_queued": notifications_queued,
    }
    logger.info("kpi_alerts_task: %s", payload)
    return payload


def _format_kpi_alerts(alerts: list) -> str:
    """Алерт-сообщение для TG."""
    lines = ["🚨 <b>KPI-алерты по откорму</b>", ""]
    for a in alerts[:15]:
        lines.append(
            f"• {a.batch_doc} · {a.kind}: <b>{a.value}</b> "
            f"(норма {a.threshold}) · день {a.day_of_age}",
        )
    if len(alerts) > 15:
        lines.append(f"…и ещё {len(alerts) - 15} алертов")
    lines.append("")
    lines.append("Откройте партию в ERP для деталей.")
    return "\n".join(lines)
