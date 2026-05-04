"""
Расчёт FCR (Feed Conversion Ratio — коэффициент конверсии корма).

FCR = расход корма (кг) / прирост массы (кг)

Хорошие значения для бройлера: 1.6–1.8. Для несушки на ремонт: 2.0–2.5.
Чем меньше FCR — тем эффективнее работает откорм.

Содержит helper-функции для:
  - суммарных расчётов FCR/прироста по партии
  - расчёта периодного FCR (на момент создания FeedlotFeedConsumption)
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.db.models import Sum

from ..models import DailyWeighing, FeedlotBatch, FeedlotFeedConsumption


_KG_QUANT = Decimal("0.001")
_FCR_QUANT = Decimal("0.001")


def _q_kg(v: Decimal) -> Decimal:
    return v.quantize(_KG_QUANT, rounding=ROUND_HALF_UP)


def _q_fcr(v: Decimal) -> Decimal:
    return v.quantize(_FCR_QUANT, rounding=ROUND_HALF_UP)


@dataclass
class FeedlotKpi:
    days_on_feedlot: int
    initial_heads: int
    current_heads: int
    dead_count: int
    survival_pct: Decimal
    total_mortality_pct: Decimal
    current_avg_weight_kg: Optional[Decimal]
    initial_avg_weight_kg: Optional[Decimal]
    total_gain_kg: Decimal
    total_feed_kg: Decimal
    total_fcr: Optional[Decimal]


def get_latest_weighing(feedlot_batch: FeedlotBatch) -> Optional[DailyWeighing]:
    """Последнее по day_of_age взвешивание."""
    return (
        DailyWeighing.objects.filter(feedlot_batch=feedlot_batch)
        .order_by("-day_of_age")
        .first()
    )


def get_first_weighing(feedlot_batch: FeedlotBatch) -> Optional[DailyWeighing]:
    """Первое по day_of_age взвешивание (стартовый вес)."""
    return (
        DailyWeighing.objects.filter(feedlot_batch=feedlot_batch)
        .order_by("day_of_age")
        .first()
    )


def get_weighing_at_or_before_day(
    feedlot_batch: FeedlotBatch, day: int,
) -> Optional[DailyWeighing]:
    """
    Ближайшее взвешивание на день <= day. Для расчёта периодного прироста.
    """
    return (
        DailyWeighing.objects.filter(feedlot_batch=feedlot_batch, day_of_age__lte=day)
        .order_by("-day_of_age")
        .first()
    )


def total_feed_kg(feedlot_batch: FeedlotBatch) -> Decimal:
    """Σ скормленного корма по всем периодам."""
    agg = FeedlotFeedConsumption.objects.filter(
        feedlot_batch=feedlot_batch
    ).aggregate(s=Sum("total_kg"))
    return _q_kg(Decimal(agg["s"] or 0))


def total_gain_kg(feedlot_batch: FeedlotBatch) -> Decimal:
    """
    Суммарный прирост массы партии.

    gain = (avg_last − avg_first) × current_heads.
    Если взвешиваний нет — возвращаем 0.
    """
    last = get_latest_weighing(feedlot_batch)
    first = get_first_weighing(feedlot_batch)
    if not last or not first:
        return Decimal("0")
    avg_first = Decimal(first.avg_weight_kg)
    avg_last = Decimal(last.avg_weight_kg)
    current = Decimal(feedlot_batch.current_heads or 0)
    # Прирост = (конечный вес - начальный вес) × выжившее поголовье.
    # Старая формула avg_last*current - avg_first*initial давала завышенный
    # прирост при падеже (учитывала исчезнувший вес павших как прирост).
    gain = (avg_last - avg_first) * current
    if gain < 0:
        gain = Decimal("0")
    return _q_kg(gain)


def compute_fcr(feed_kg: Decimal, gain_kg: Decimal) -> Optional[Decimal]:
    """FCR = feed / gain. Если gain<=0 — None."""
    if gain_kg is None or gain_kg <= 0:
        return None
    return _q_fcr(Decimal(feed_kg) / Decimal(gain_kg))


def compute_period_fcr(
    feedlot_batch: FeedlotBatch,
    period_from_day: int,
    period_to_day: int,
    period_feed_kg: Decimal,
) -> Optional[Decimal]:
    """
    FCR за период = period_feed_kg / period_gain_kg.

    period_gain_kg = (avg_at_to − avg_at_from) × current_heads_in_period.

    Если на одной из границ нет взвешивания — None.
    """
    w_from = get_weighing_at_or_before_day(feedlot_batch, period_from_day)
    w_to = get_weighing_at_or_before_day(feedlot_batch, period_to_day)
    if not w_from or not w_to:
        return None
    if w_from.id == w_to.id:
        # Период без прироста (одно взвешивание) — FCR не считаем
        return None
    delta = Decimal(w_to.avg_weight_kg) - Decimal(w_from.avg_weight_kg)
    if delta <= 0:
        return None
    heads = Decimal(feedlot_batch.current_heads or 0)
    gain = delta * heads
    return compute_fcr(Decimal(period_feed_kg), gain)


def get_kpi(feedlot_batch: FeedlotBatch) -> FeedlotKpi:
    """Полный KPI-набор для drawer'а / stats action."""
    from datetime import date as date_cls

    today = date_cls.today()
    days = (today - feedlot_batch.placed_date).days if feedlot_batch.placed_date else 0
    if days < 0:
        days = 0

    initial = feedlot_batch.initial_heads or 0
    current = feedlot_batch.current_heads or 0
    dead = max(0, initial - current)
    survival = (
        (Decimal(current) / Decimal(initial) * Decimal("100")).quantize(Decimal("0.01"))
        if initial > 0 else Decimal("0")
    )
    mortality_pct = (
        (Decimal(dead) / Decimal(initial) * Decimal("100")).quantize(Decimal("0.01"))
        if initial > 0 else Decimal("0")
    )

    last = get_latest_weighing(feedlot_batch)
    first = get_first_weighing(feedlot_batch)

    feed = total_feed_kg(feedlot_batch)
    gain = total_gain_kg(feedlot_batch)
    fcr = compute_fcr(feed, gain) if gain > 0 else None

    return FeedlotKpi(
        days_on_feedlot=days,
        initial_heads=initial,
        current_heads=current,
        dead_count=dead,
        survival_pct=survival,
        total_mortality_pct=mortality_pct,
        current_avg_weight_kg=Decimal(last.avg_weight_kg) if last else None,
        initial_avg_weight_kg=Decimal(first.avg_weight_kg) if first else None,
        total_gain_kg=gain,
        total_feed_kg=feed,
        total_fcr=fcr,
    )
