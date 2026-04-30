"""
Проверка KPI откорма на превышение порогов.

Вызывается ежедневной Celery-таской `apps.feedlot.kpi_alerts_task`.
Обнаруженные алерты передаются в TG через `notify_admins_task` с
`module_code="feedlot"` (получают только пользователи с feed-доступом).

Пороги — из `settings`:
  FEEDLOT_MORTALITY_ALERT_PCT (default 5.0) — % падежа от initial
  FEEDLOT_FCR_ALERT_VALUE     (default 2.0) — FCR выше этого = плохо
  FEEDLOT_FCR_ALERT_MIN_DAY   (default 14)  — не алертим раньше этого дня
                                              (FCR на старте шумный)

Возможно расширение: per-organization пороги через JSON-поле на Organization
(пока не делаем — добавим если будут реальные жалобы про шум).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal
from typing import Iterable

from django.conf import settings


@dataclass
class KpiAlert:
    batch_id: str
    batch_doc: str
    house_code: str
    kind: str            # "mortality" | "fcr"
    value: str           # текущее значение, форматированное
    threshold: str       # пороговое значение
    day_of_age: int


def _mortality_threshold() -> Decimal:
    return Decimal(str(getattr(settings, "FEEDLOT_MORTALITY_ALERT_PCT", 5.0)))


def _fcr_threshold() -> Decimal:
    return Decimal(str(getattr(settings, "FEEDLOT_FCR_ALERT_VALUE", 2.0)))


def _fcr_min_day() -> int:
    return int(getattr(settings, "FEEDLOT_FCR_ALERT_MIN_DAY", 14))


def collect_org_alerts(organization) -> list[KpiAlert]:
    """Собрать KPI-алерты по всем активным партиям откорма организации."""
    from ..models import FeedlotBatch
    from . import fcr as fcr_service

    today = _date.today()
    active_statuses = [
        FeedlotBatch.Status.PLACED,
        FeedlotBatch.Status.GROWING,
        FeedlotBatch.Status.READY_SLAUGHTER,
    ]

    batches = list(
        FeedlotBatch.objects.filter(
            organization=organization,
            status__in=active_statuses,
        ).select_related("house_block")
    )
    if not batches:
        return []

    mortality_threshold = _mortality_threshold()
    fcr_threshold = _fcr_threshold()
    fcr_min_day = _fcr_min_day()
    alerts: list[KpiAlert] = []

    for b in batches:
        day = (today - b.placed_date).days if b.placed_date else 0

        # Mortality % = (initial - current) / initial * 100
        if b.initial_heads and b.initial_heads > 0:
            dead = max(0, (b.initial_heads or 0) - (b.current_heads or 0))
            mort_pct = (Decimal(dead) / Decimal(b.initial_heads)) * Decimal("100")
            if mort_pct > mortality_threshold:
                alerts.append(KpiAlert(
                    batch_id=str(b.id),
                    batch_doc=b.doc_number,
                    house_code=getattr(b.house_block, "code", "—"),
                    kind="падёж %",
                    value=f"{mort_pct.quantize(Decimal('0.01'))}%",
                    threshold=f"{mortality_threshold}%",
                    day_of_age=day,
                ))

        # FCR — только если партия достаточно «прожила» (раньше шум)
        if day >= fcr_min_day:
            feed = fcr_service.total_feed_kg(b)
            gain = fcr_service.total_gain_kg(b)
            fcr = fcr_service.compute_fcr(feed, gain) if gain > 0 else None
            if fcr is not None and fcr > fcr_threshold:
                alerts.append(KpiAlert(
                    batch_id=str(b.id),
                    batch_doc=b.doc_number,
                    house_code=getattr(b.house_block, "code", "—"),
                    kind="FCR",
                    value=str(fcr),
                    threshold=str(fcr_threshold),
                    day_of_age=day,
                ))

    return alerts


def collect_all_alerts() -> Iterable[KpiAlert]:
    """Альтернативный entry-point если хочется одним списком по всем организациям."""
    from apps.organizations.models import Organization

    for org in Organization.objects.filter(is_active=True).iterator():
        yield from collect_org_alerts(org)
