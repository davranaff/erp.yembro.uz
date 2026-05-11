"""
FX-helpers для payroll.

Принцип: SalaryRate хранит сумму в native currency (UZS, USD, EUR). При
расчёте accrued/balance каждая нативная сумма конвертируется в UZS по курсу
CBU на shift_date (live). Курсовые разницы между accrue и payout
компенсируются live-пересчётом — баланс всегда отражает актуальный долг.

UZS-ставки идут без конвертации (rate=1, нет ExchangeRate-snapshot).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional


@dataclass
class FXConversion:
    """Результат конвертации native_amount в UZS."""
    amount_native: Decimal
    currency_code: str
    amount_uzs: Decimal
    exchange_rate: Decimal  # UZS за 1 единицу currency
    rate_date: Optional[date]  # дата курса (может != on_date из-за fallback)


def convert_to_uzs(
    amount: Decimal,
    currency_code: str,
    on_date: date,
) -> FXConversion:
    """
    Конвертировать native_amount → UZS по курсу CBU на on_date (с fallback
    до FX_FALLBACK_DAYS дней).

    Для UZS возвращает rate=1 без обращения к ExchangeRate.

    Raises:
        django.core.exceptions.ValidationError если курс не найден.
    """
    code = (currency_code or "").upper()
    if code in ("UZS", ""):
        return FXConversion(
            amount_native=amount,
            currency_code="UZS",
            amount_uzs=amount,
            exchange_rate=Decimal("1"),
            rate_date=None,
        )

    from apps.currency.selectors import get_rate_for

    rate_obj = get_rate_for(code, on_date)
    nominal = Decimal(str(rate_obj.nominal or 1))
    unit_rate = (Decimal(str(rate_obj.rate)) / nominal)
    amount_uzs = (amount * unit_rate).quantize(Decimal("0.01"))
    return FXConversion(
        amount_native=amount,
        currency_code=code,
        amount_uzs=amount_uzs,
        exchange_rate=unit_rate,
        rate_date=rate_obj.date,
    )
