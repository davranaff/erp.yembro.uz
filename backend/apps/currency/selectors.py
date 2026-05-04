"""
Read-layer helpers for currency/ExchangeRate.

`get_rate_for(currency_code, on_date)` — основная точка входа для других
модулей (confirm_purchase, post_payment), которым нужен курс на конкретную
дату. Делает fallback до N дней назад, если точного курса нет (например
выходной день на CBU).
"""
from datetime import date, timedelta
from typing import Optional

from django.conf import settings
from django.core.exceptions import ValidationError


DEFAULT_FALLBACK_DAYS = 7


def _fallback_days_default() -> int:
    return getattr(settings, "FX_FALLBACK_DAYS", DEFAULT_FALLBACK_DAYS)


def get_rate_for(
    currency_code: str,
    on_date: date,
    *,
    fallback_days: Optional[int] = None,
    source: Optional[str] = None,
):
    """
    Вернуть `ExchangeRate` для валюты и даты.

    Если точного курса нет, ищет последнюю доступную запись за
    `fallback_days` дней до `on_date`. Если ничего не найдено —
    выбрасывает `ValidationError` — каллер должен его обработать.

    Args:
        currency_code: "USD", "EUR" и т.п. (case-insensitive).
        on_date: целевая дата операции.
        fallback_days: сколько дней назад допустимо «откатиться» (default 7).
        source: опциональный фильтр по источнику курса.

    Returns:
        ExchangeRate instance.

    Raises:
        ValidationError: если курса нет ни на дату, ни в окне fallback.
    """
    from .models import Currency, ExchangeRate

    code = currency_code.upper()
    if fallback_days is None:
        fallback_days = _fallback_days_default()

    try:
        currency = Currency.objects.get(code=code)
    except Currency.DoesNotExist as exc:
        raise ValidationError(
            {"currency": f"Валюта '{code}' не найдена в справочнике."}
        ) from exc

    min_date = on_date - timedelta(days=fallback_days)
    qs = ExchangeRate.objects.filter(
        currency=currency,
        date__lte=on_date,
        date__gte=min_date,
    )
    if source:
        qs = qs.filter(source=source)

    rate = qs.order_by("-date").first()
    if rate is None:
        raise ValidationError(
            {
                "currency": (
                    f"Нет курса для {code} на {on_date} "
                    f"(искали до {fallback_days} дней назад)."
                )
            }
        )
    return rate


def get_latest_rate(currency_code: str, *, source: Optional[str] = None):
    """
    Последний доступный курс по валюте (без ограничения по дате).
    """
    from .models import Currency, ExchangeRate

    code = currency_code.upper()
    try:
        currency = Currency.objects.get(code=code)
    except Currency.DoesNotExist as exc:
        raise ValidationError(
            {"currency": f"Валюта '{code}' не найдена."}
        ) from exc

    qs = ExchangeRate.objects.filter(currency=currency)
    if source:
        qs = qs.filter(source=source)
    return qs.order_by("-date").first()
