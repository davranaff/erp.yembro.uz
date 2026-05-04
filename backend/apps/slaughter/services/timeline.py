"""
Сервис `get_shift_timeline` — единый таймлайн событий смены убоя.

События: created, quality, lab, yield, posted, reversed.
Возвращает list[dict] отсортированный по дате (asc).
"""
from __future__ import annotations

from typing import Any

from ..models import SlaughterShift


def _fmt_date(dt) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "date"):
        return dt.date().isoformat()
    return dt.isoformat()


def get_shift_timeline(shift: SlaughterShift) -> list[dict[str, Any]]:
    """Собрать события смены в единый отсортированный список."""
    events: list[dict[str, Any]] = []

    # Создание смены
    events.append(
        {
            "type": "created",
            "id": str(shift.id),
            "date": _fmt_date(shift.created_at),
            "title": f"Смена создана · {shift.doc_number}",
            "subtitle": (
                f"{shift.live_heads_received} гол · "
                f"{shift.live_weight_kg_total} кг живого веса"
            ),
            "notes": shift.notes or "",
        }
    )

    # Контроль качества (1:1)
    qc = getattr(shift, "quality_check", None)
    if qc is not None:
        flag = "✓" if qc.vet_inspection_passed else "✗"
        sub_parts = []
        if qc.carcass_defect_percent is not None:
            sub_parts.append(f"дефект {qc.carcass_defect_percent}%")
        if qc.trauma_percent is not None:
            sub_parts.append(f"травмы {qc.trauma_percent}%")
        if qc.cooling_temperature_c is not None:
            sub_parts.append(f"t {qc.cooling_temperature_c}°C")
        events.append(
            {
                "type": "quality",
                "id": str(qc.id),
                "date": _fmt_date(qc.inspected_at),
                "title": f"Контроль качества {flag}",
                "subtitle": " · ".join(sub_parts) or "осмотр выполнен",
                "notes": qc.notes or "",
            }
        )

    # Лабораторные тесты
    for lt in shift.lab_tests.all():
        date = lt.result_at or lt.sampled_at or lt.created_at
        events.append(
            {
                "type": "lab",
                "id": str(lt.id),
                "date": _fmt_date(date),
                "title": f"{lt.indicator} · {lt.get_status_display()}",
                "subtitle": (
                    f"норма {lt.normal_range} · факт {lt.actual_value}"
                ),
                "notes": lt.notes or "",
            }
        )

    # Выходы продукции
    for y in shift.yields.select_related("nomenclature", "unit"):
        events.append(
            {
                "type": "yield",
                "id": str(y.id),
                "date": _fmt_date(y.created_at),
                "title": f"Выход · {y.nomenclature.sku}",
                "subtitle": (
                    f"{y.quantity} {y.unit.code}"
                    + (
                        f" · доля {y.share_percent}%"
                        if y.share_percent is not None
                        else ""
                    )
                ),
                "notes": y.notes or "",
            }
        )

    # Финал: posted / cancelled
    if shift.status == SlaughterShift.Status.POSTED:
        events.append(
            {
                "type": "posted",
                "id": str(shift.id),
                "date": _fmt_date(shift.end_time or shift.updated_at),
                "title": "Смена проведена",
                "subtitle": "JE и StockMovement созданы",
                "notes": "",
            }
        )
    elif shift.status == SlaughterShift.Status.CANCELLED:
        events.append(
            {
                "type": "reversed",
                "id": str(shift.id),
                "date": _fmt_date(shift.updated_at),
                "title": "Смена отменена",
                "subtitle": "Проводки сторнированы",
                "notes": "",
            }
        )

    events.sort(key=lambda e: e["date"])
    return events
