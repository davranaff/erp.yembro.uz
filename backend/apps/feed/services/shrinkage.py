"""
Расчёт усушки сырья при приёмке (формула Дюваля + сорность).

Контекст: на комбикормовых заводах CIS зерно и шрот приезжают с
влажностью, отличной от базисной (14% по ГОСТ 13586.5 для зерна,
обычно 12% для шрота). На склад принимается не физический вес, а
**зачётный** — пересчитанный по формуле Дюваля:

    Хв = 100 × (A − B) / (100 − B)

где A — фактическая влажность %, B — базисная влажность %, Хв —
процент потери массы относительно физического веса.

Поправка на сорность складывается аддитивно (упрощение для MVP;
строгая методика в ГОСТ — иная, но для бухгалтерии достаточно).

Все функции — чистые, без обращения к БД.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Optional


_PCT_QUANT = Decimal("0.01")
_KG_QUANT = Decimal("0.001")
_HUNDRED = Decimal("100")


def _q_pct(v: Decimal) -> Decimal:
    return v.quantize(_PCT_QUANT, rounding=ROUND_HALF_UP)


def _q_kg(v: Decimal) -> Decimal:
    return v.quantize(_KG_QUANT, rounding=ROUND_HALF_UP)


def duval_shrinkage_pct(actual_moisture: Decimal, base_moisture: Decimal) -> Decimal:
    """
    Формула Дюваля: процент усушки относительно физического веса.

    >>> duval_shrinkage_pct(Decimal("18"), Decimal("14"))
    Decimal('4.65')

    Если фактическая влажность <= базисной — усушки нет (возвращаем 0).
    """
    if actual_moisture is None or base_moisture is None:
        return Decimal("0")
    if actual_moisture <= base_moisture:
        return Decimal("0")
    denom = _HUNDRED - base_moisture
    if denom <= 0:
        return Decimal("0")
    pct = _HUNDRED * (actual_moisture - base_moisture) / denom
    return _q_pct(pct)


def settlement_from_gross(gross_kg: Decimal, shrink_pct: Decimal) -> Decimal:
    """
    settlement = gross × (1 − shrink/100). Не меньше нуля.
    """
    if gross_kg is None or gross_kg <= 0:
        return Decimal("0")
    if shrink_pct is None or shrink_pct <= 0:
        return _q_kg(gross_kg)
    factor = (_HUNDRED - shrink_pct) / _HUNDRED
    res = gross_kg * factor
    if res < 0:
        res = Decimal("0")
    return _q_kg(res)


def compute_settlement(
    *,
    gross_kg: Decimal,
    moisture_actual: Optional[Decimal] = None,
    moisture_base: Optional[Decimal] = None,
    dockage_actual: Optional[Decimal] = None,
) -> tuple[Decimal, Decimal]:
    """
    Полный расчёт зачётного веса.

    Возвращает кортеж `(settlement_weight_kg, total_shrinkage_pct)`.

    Логика:
      - если moisture_actual + moisture_base заданы → +duval_shrinkage_pct
      - dockage_actual прибавляется к итогу
      - если ни того ни другого — total_shrink = 0 → settlement = gross

    Примеры:
      gross=10000, moist_actual=18, moist_base=14, dockage=0 → (9535.0, 4.65)
      gross=10000, moist_actual=14, moist_base=14, dockage=2 → (9800.0, 2.00)
      gross=10000, dockage=3                                 → (9700.0, 3.00)
    """
    duval = (
        duval_shrinkage_pct(moisture_actual, moisture_base)
        if (moisture_actual is not None and moisture_base is not None)
        else Decimal("0")
    )
    dockage = dockage_actual if dockage_actual is not None else Decimal("0")
    total = _q_pct(duval + dockage)
    settlement = settlement_from_gross(gross_kg, total)
    return settlement, total
