"""
KPI сервис для смены убоя: yield %, output kg, defect rate, lab counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from ..models import SlaughterLabTest, SlaughterShift


CARCASS_SKU_PREFIXES = ("CARCASS",)  # «Тушка целая»
KG_CODES = {"kg", "кг"}

# Стандартные нормы выхода по бройлеру (% от живого веса).
# Источник: усреднённые отраслевые показатели для бройлера ROSS-308 / COBB-500.
BROILER_YIELD_NORMS: dict[str, Decimal] = {
    "CARCASS-WHOLE": Decimal("72.00"),
    "BREAST":        Decimal("25.00"),
    "LEG":           Decimal("28.00"),
    "WING":          Decimal("8.50"),
    "OFFAL":         Decimal("8.00"),
    "FEET":          Decimal("4.00"),
    "HEAD":          Decimal("3.00"),
    "NECK":          Decimal("3.50"),
}
# Допустимое отклонение факт vs норма (абс. % от живого веса).
YIELD_TOLERANCE = Decimal("2.00")


@dataclass
class SlaughterYieldBreakdownRow:
    sku: str
    name: str
    quantity_kg: Decimal
    yield_pct: Optional[Decimal]   # % от живого веса
    norm_pct: Optional[Decimal]    # норма по бройлеру
    deviation_pct: Optional[Decimal]  # факт − норма
    is_within_tolerance: bool


@dataclass
class SlaughterShiftKpi:
    total_output_kg: Decimal
    total_output_pct: Optional[Decimal]   # Σ выходов / живой вес × 100
    waste_kg: Optional[Decimal]           # живой вес − Σ выходов
    waste_pct: Optional[Decimal]          # 100 − total_output_pct
    carcass_kg: Decimal
    carcass_yield_pct: Optional[Decimal]
    yield_per_head_kg: Optional[Decimal]
    defect_rate: Optional[Decimal]
    quality_checked: bool
    yields_count: int
    lab_pending_count: int
    lab_passed_count: int
    lab_failed_count: int
    breakdown: list["SlaughterYieldBreakdownRow"]


def compute_yield_pct(quantity_kg: Decimal, live_kg: Decimal) -> Optional[Decimal]:
    if live_kg is None or live_kg <= 0:
        return None
    return (quantity_kg / live_kg * Decimal("100")).quantize(Decimal("0.01"))


def get_shift_kpi(shift: SlaughterShift) -> SlaughterShiftKpi:
    yields = list(shift.yields.select_related("nomenclature", "unit"))
    live_kg = shift.live_weight_kg_total or Decimal("0")

    total_kg = sum(
        (y.quantity for y in yields if y.unit and y.unit.code.lower() in KG_CODES),
        Decimal("0"),
    )

    carcass_kg = sum(
        (
            y.quantity
            for y in yields
            if y.unit
            and y.unit.code.lower() in KG_CODES
            and any(
                y.nomenclature.sku.upper().startswith(p)
                for p in CARCASS_SKU_PREFIXES
            )
        ),
        Decimal("0"),
    )

    if live_kg > 0:
        carcass_yield_pct = compute_yield_pct(carcass_kg, live_kg)
        total_output_pct = compute_yield_pct(total_kg, live_kg)
        waste_kg = (live_kg - total_kg).quantize(Decimal("0.001"))
        waste_pct = (Decimal("100.00") - (total_output_pct or Decimal("0"))).quantize(
            Decimal("0.01")
        )
    else:
        carcass_yield_pct = None
        total_output_pct = None
        waste_kg = None
        waste_pct = None

    if shift.live_heads_received > 0 and total_kg > 0:
        yield_per_head_kg = (total_kg / shift.live_heads_received).quantize(
            Decimal("0.001")
        )
    else:
        yield_per_head_kg = None

    # Breakdown по каждому SKU с нормами
    breakdown: list[SlaughterYieldBreakdownRow] = []
    for y in yields:
        if not y.unit or y.unit.code.lower() not in KG_CODES:
            continue
        sku = y.nomenclature.sku
        yield_pct = compute_yield_pct(y.quantity, live_kg)
        norm = BROILER_YIELD_NORMS.get(sku.upper())
        if yield_pct is not None and norm is not None:
            deviation = (yield_pct - norm).quantize(Decimal("0.01"))
            within_tol = abs(deviation) <= YIELD_TOLERANCE
        else:
            deviation = None
            within_tol = True  # нет нормы → не оцениваем
        breakdown.append(
            SlaughterYieldBreakdownRow(
                sku=sku,
                name=y.nomenclature.name,
                quantity_kg=y.quantity,
                yield_pct=yield_pct,
                norm_pct=norm,
                deviation_pct=deviation,
                is_within_tolerance=within_tol,
            )
        )

    qc = getattr(shift, "quality_check", None)
    defect_rate = qc.carcass_defect_percent if qc else None
    quality_checked = bool(qc and qc.vet_inspection_passed)

    lab_qs = SlaughterLabTest.objects.filter(shift=shift)
    lab_pending = lab_qs.filter(status=SlaughterLabTest.Status.PENDING).count()
    lab_passed = lab_qs.filter(status=SlaughterLabTest.Status.PASSED).count()
    lab_failed = lab_qs.filter(status=SlaughterLabTest.Status.FAILED).count()

    return SlaughterShiftKpi(
        total_output_kg=total_kg,
        total_output_pct=total_output_pct,
        waste_kg=waste_kg,
        waste_pct=waste_pct,
        carcass_kg=carcass_kg,
        carcass_yield_pct=carcass_yield_pct,
        yield_per_head_kg=yield_per_head_kg,
        defect_rate=defect_rate,
        quality_checked=quality_checked,
        yields_count=len(yields),
        lab_pending_count=lab_pending,
        lab_passed_count=lab_passed,
        lab_failed_count=lab_failed,
        breakdown=breakdown,
    )
