"""
Проверка KPI родительского стада (маточник).

Алерты:
  - low_productivity — средняя яйценоскость за неделю ниже порога
    (default 50%) для стад в статусе PRODUCING и достаточного возраста
  - high_mortality — недельный падёж больше threshold % от current_heads
    (default 1.0% — для несушек норма ≤ 0.1% в неделю, 1% — серьёзный сигнал)

Молодые стада (`current_age_weeks < MIN_AGE_WEEKS`) игнорируем —
они ещё не вышли на пик, нулевая яйценоскость — норма.

Пороги настраиваются через settings:
  MATOCHNIK_LOW_PRODUCTIVITY_ALERT_PCT  default 50.0
  MATOCHNIK_MORTALITY_ALERT_PCT_WEEK    default 1.0
  MATOCHNIK_PRODUCTIVITY_MIN_AGE_WEEKS  default 22
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date, timedelta
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db.models import Sum


@dataclass
class HerdAlert:
    herd_id: str
    herd_doc: str
    block_code: str
    kind: str            # "продуктивность" | "падёж/нед"
    value: str           # текущее значение, форматированное
    threshold: str       # порог
    note: str            # короткий поясняющий хвост


def _low_prod_pct() -> Decimal:
    return Decimal(str(getattr(settings, "MATOCHNIK_LOW_PRODUCTIVITY_ALERT_PCT", 50.0)))


def _mort_pct_week() -> Decimal:
    return Decimal(str(getattr(settings, "MATOCHNIK_MORTALITY_ALERT_PCT_WEEK", 1.0)))


def _min_age_weeks() -> int:
    return int(getattr(settings, "MATOCHNIK_PRODUCTIVITY_MIN_AGE_WEEKS", 22))


def _current_age_weeks(herd, today: _date) -> int:
    if not herd.placed_at:
        return herd.age_weeks_at_placement or 0
    delta_days = (today - herd.placed_at).days
    if delta_days < 0:
        delta_days = 0
    return (herd.age_weeks_at_placement or 0) + (delta_days // 7)


def collect_org_alerts(organization) -> list[HerdAlert]:
    """Собрать KPI-алерты по всем активным стадам организации."""
    from ..models import (
        BreedingHerd,
        BreedingMortality,
        DailyEggProduction,
    )

    today = _date.today()
    week_start = today - timedelta(days=6)  # 7 дней включая сегодня

    active_statuses = [
        BreedingHerd.Status.GROWING,
        BreedingHerd.Status.PRODUCING,
    ]

    herds = list(
        BreedingHerd.objects.filter(
            organization=organization,
            status__in=active_statuses,
        ).select_related("block")
    )
    if not herds:
        return []

    low_prod = _low_prod_pct()
    mort_threshold = _mort_pct_week()
    min_age = _min_age_weeks()
    alerts: list[HerdAlert] = []

    herd_ids = [h.id for h in herds]

    eggs_by_herd = dict(
        DailyEggProduction.objects
        .filter(herd_id__in=herd_ids, date__gte=week_start, date__lte=today)
        .values_list("herd_id")
        .annotate(s=Sum("eggs_collected"))
        .values_list("herd_id", "s")
    )
    unfit_by_herd = dict(
        DailyEggProduction.objects
        .filter(herd_id__in=herd_ids, date__gte=week_start, date__lte=today)
        .values_list("herd_id")
        .annotate(s=Sum("unfit_eggs"))
        .values_list("herd_id", "s")
    )
    mort_by_herd = dict(
        BreedingMortality.objects
        .filter(herd_id__in=herd_ids, date__gte=week_start, date__lte=today)
        .values_list("herd_id")
        .annotate(s=Sum("dead_count"))
        .values_list("herd_id", "s")
    )

    for h in herds:
        block_code = getattr(h.block, "code", "—") if h.block_id else "—"
        age = _current_age_weeks(h, today)
        current_heads = h.current_heads or 0

        # ── Продуктивность: только для PRODUCING + взрослых стад ──────────
        if (
            h.status == BreedingHerd.Status.PRODUCING
            and age >= min_age
            and current_heads > 0
        ):
            collected = eggs_by_herd.get(h.id, 0) or 0
            unfit = unfit_by_herd.get(h.id, 0) or 0
            clean = max(0, collected - unfit)
            # средняя % за окно: clean / (heads * days)
            denom = Decimal(current_heads) * Decimal(7)
            avg_pct = (
                Decimal(clean) / denom * Decimal("100")
                if denom > 0 else Decimal("0")
            )
            if avg_pct < low_prod:
                alerts.append(HerdAlert(
                    herd_id=str(h.id),
                    herd_doc=h.doc_number,
                    block_code=block_code,
                    kind="продуктивность",
                    value=f"{avg_pct.quantize(Decimal('0.01'))}%",
                    threshold=f"{low_prod}%",
                    note=f"за 7 дней · возраст {age} нед",
                ))

        # ── Падёж (для всех активных стад, независимо от продуктивности) ──
        if current_heads > 0:
            dead = mort_by_herd.get(h.id, 0) or 0
            mort_pct = (Decimal(dead) / Decimal(current_heads) * Decimal("100"))
            if mort_pct > mort_threshold:
                alerts.append(HerdAlert(
                    herd_id=str(h.id),
                    herd_doc=h.doc_number,
                    block_code=block_code,
                    kind="падёж/нед",
                    value=f"{mort_pct.quantize(Decimal('0.01'))}%",
                    threshold=f"{mort_threshold}%",
                    note=f"{dead} гол · из {current_heads}",
                ))

    return alerts


def collect_all_alerts() -> Iterable[HerdAlert]:
    from apps.organizations.models import Organization

    for org in Organization.objects.filter(is_active=True).iterator():
        yield from collect_org_alerts(org)
