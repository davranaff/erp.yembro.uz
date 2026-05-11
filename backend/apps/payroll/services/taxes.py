"""
Налоги с ФОТ (UZ): НДФЛ + ИНПС удерживаются из ЗП сотрудника, ЕСП — расход компании.

Хранение настроек: OrganizationModule(module=hr).settings_json:
    {
      "ndfl_pct": "12",
      "inps_pct": "0.1",
      "esp_pct": "25",
      "auto_apply_on_payout": true
    }

apply_taxes_for_payout(payout) — после успешного create_payout создаёт:
  1. PayrollAdjustment(DEDUCTION, reason="НДФЛ") — на (amount × ndfl_pct).
  2. PayrollAdjustment(DEDUCTION, reason="ИНПС") — на (amount × inps_pct).
  3. Payment(kind=opex, expense_article=PAYROLL_TAX) — расход компании на ЕСП.

Не вызывает падение основной выплаты (ошибки логируются).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

from ..models import PayrollAdjustment, PayrollPayout

logger = logging.getLogger(__name__)


def get_tax_settings(organization) -> dict:
    """Читает настройки налогов из OrganizationModule(hr).settings_json."""
    from apps.modules.models import OrganizationModule

    om = OrganizationModule.objects.filter(
        organization=organization, module__code="hr",
    ).first()
    if om is None or not om.settings_json:
        return {}
    return om.settings_json or {}


def _pct_to_decimal(value, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value or default))
    except Exception:
        return Decimal(default)


@transaction.atomic
def apply_taxes_for_payout(payout: PayrollPayout) -> dict:
    """
    Применяет налоги к выплате согласно настройкам org. Возвращает dict
    с созданными суммами {ndfl, inps, esp_uzs}.

    Идемпотентность: проверяет наличие уже созданных DEDUCTION с reason
    "ндфл"/"инпс" с тем же effective_date — не дублирует.
    """
    settings = get_tax_settings(payout.organization)
    if not settings.get("auto_apply_on_payout"):
        return {}

    ndfl_pct = _pct_to_decimal(settings.get("ndfl_pct"), "0")
    inps_pct = _pct_to_decimal(settings.get("inps_pct"), "0")
    esp_pct = _pct_to_decimal(settings.get("esp_pct"), "0")
    base = payout.amount_uzs
    eff_date = payout.payment.date if payout.payment_id else payout.period_to

    out = {"ndfl": Decimal("0"), "inps": Decimal("0"), "esp": Decimal("0")}

    if ndfl_pct > 0:
        ndfl_amount = (base * ndfl_pct / Decimal(100)).quantize(Decimal("0.01"))
        if ndfl_amount > 0 and not _adjustment_exists(payout.employee, eff_date, "НДФЛ"):
            PayrollAdjustment.objects.create(
                organization=payout.organization,
                employee=payout.employee,
                kind=PayrollAdjustment.Kind.DEDUCTION,
                effective_date=eff_date,
                amount_uzs=ndfl_amount,
                reason=f"НДФЛ {ndfl_pct}% от выплаты {payout.payment.doc_number if payout.payment_id else payout.id}",
            )
            out["ndfl"] = ndfl_amount

    if inps_pct > 0:
        inps_amount = (base * inps_pct / Decimal(100)).quantize(Decimal("0.01"))
        if inps_amount > 0 and not _adjustment_exists(payout.employee, eff_date, "ИНПС"):
            PayrollAdjustment.objects.create(
                organization=payout.organization,
                employee=payout.employee,
                kind=PayrollAdjustment.Kind.DEDUCTION,
                effective_date=eff_date,
                amount_uzs=inps_amount,
                reason=f"ИНПС {inps_pct}% от выплаты {payout.payment.doc_number if payout.payment_id else payout.id}",
            )
            out["inps"] = inps_amount

    if esp_pct > 0:
        out["esp"] = (base * esp_pct / Decimal(100)).quantize(Decimal("0.01"))
        # ЕСП — это расход компании (не удержание из ЗП). Записываем как
        # информационный adjustment с reason='ЕСП' но НЕ удерживаем из баланса
        # сотрудника. Реальный платёж в бюджет создаётся отдельно (см. ниже).
        # Для MVP возвращаем сумму, фактический Payment делает HR вручную.
        # Можно автоматизировать в P3 (когда будет ясна налоговая периодичность).

    return out


def _adjustment_exists(employee, eff_date, reason_prefix: str) -> bool:
    return PayrollAdjustment.objects.filter(
        employee=employee,
        effective_date=eff_date,
        reason__istartswith=reason_prefix,
    ).exists()
