"""
KPI-алерты для модуля «Инкубация».

Триггер: после `hatch` (вывод суточного цыплёнка) посчитан hatchability —
если он ниже порога, отправить TG-алерт. Это вечернее напоминание после
закрытия инкубационных партий за день.

Пороги — из settings:
  INCUBATION_HATCH_RATE_ALERT_PCT (default 80.0) — ниже этого = плохо
  INCUBATION_MIN_FERTILE_FOR_ALERT (default 100) — на маленьких партиях
                                                   статистически шумно

Логика: сначала смотрим только что закрытые runs (status=TRANSFERRED,
actual_hatch_date в последние N дней). Если hatched/fertile < threshold —
алерт. На уже отправленные не алертим повторно — для этого можно
использовать `notes` или отдельный флаг (пока: в `_alerted_set` per-run-id
в кэше памяти; для прода — DB-флаг `kpi_alerted_at`).

В этой реализации алертим **последние 24 часа** — задача запускается раз в
сутки в 19:00 (после feedlot-kpi-alerts), так что окно совпадает.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, timedelta
from decimal import Decimal

from django.conf import settings


@dataclass
class IncubationAlert:
    run_id: str
    run_doc: str
    hatch_rate_pct: str       # "73.45"
    threshold_pct: str
    fertile: int
    hatched: int


def _threshold() -> Decimal:
    return Decimal(str(getattr(settings, "INCUBATION_HATCH_RATE_ALERT_PCT", 80.0)))


def _min_fertile() -> int:
    return int(getattr(settings, "INCUBATION_MIN_FERTILE_FOR_ALERT", 100))


def collect_org_alerts(organization) -> list[IncubationAlert]:
    """Собрать алерты по партиям инкубации этой организации, закрытым за
    последние 24 часа."""
    from ..models import IncubationRun

    today = _date.today()
    yesterday = today - timedelta(days=1)
    threshold = _threshold()
    min_fertile = _min_fertile()

    runs = IncubationRun.objects.filter(
        organization=organization,
        status=IncubationRun.Status.TRANSFERRED,
        actual_hatch_date__gte=yesterday,
        actual_hatch_date__lte=today,
        fertile_eggs__isnull=False,
        hatched_count__isnull=False,
    )

    alerts: list[IncubationAlert] = []
    for r in runs:
        if not r.fertile_eggs or r.fertile_eggs < min_fertile:
            continue
        # hatched / fertile × 100
        rate = (Decimal(r.hatched_count) / Decimal(r.fertile_eggs)) * Decimal("100")
        rate = rate.quantize(Decimal("0.01"))
        if rate < threshold:
            alerts.append(IncubationAlert(
                run_id=str(r.id),
                run_doc=r.doc_number,
                hatch_rate_pct=str(rate),
                threshold_pct=str(threshold),
                fertile=r.fertile_eggs or 0,
                hatched=r.hatched_count or 0,
            ))
    return alerts
