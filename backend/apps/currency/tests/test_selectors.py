"""
Тесты селекторов: get_rate_for с fallback-логикой.
"""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from apps.currency.models import Currency, ExchangeRate
from apps.currency.selectors import get_latest_rate, get_rate_for


pytestmark = pytest.mark.django_db


@pytest.fixture
def usd():
    # USD досеивается миграцией currency/0003_seed_base_currencies — берём
    # существующий, чтобы не упасть на unique constraint.
    return Currency.objects.get_or_create(
        code="USD",
        defaults={"numeric_code": "840", "name_ru": "Доллар США"},
    )[0]


def _mkrate(currency, day, rate_value=12800):
    return ExchangeRate.objects.create(
        currency=currency,
        date=day,
        rate=Decimal(str(rate_value)),
        nominal=1,
        source="cbu.uz",
        fetched_at=datetime.now(timezone.utc),
    )


def test_get_rate_exact_date(usd):
    target = date(2026, 4, 24)
    _mkrate(usd, target, 12015.96)
    rate = get_rate_for("USD", target)
    assert rate.date == target
    assert rate.rate == Decimal("12015.96")


def test_get_rate_fallback_to_previous_day(usd):
    _mkrate(usd, date(2026, 4, 20), 12000)
    rate = get_rate_for("USD", date(2026, 4, 23))
    assert rate.date == date(2026, 4, 20)


def test_get_rate_picks_latest_in_window(usd):
    _mkrate(usd, date(2026, 4, 20), 12000)
    _mkrate(usd, date(2026, 4, 22), 12100)
    rate = get_rate_for("USD", date(2026, 4, 23))
    assert rate.date == date(2026, 4, 22)
    assert rate.rate == Decimal("12100")


def test_get_rate_raises_if_outside_fallback_window(usd):
    _mkrate(usd, date(2026, 4, 1), 12000)
    with pytest.raises(ValidationError):
        get_rate_for("USD", date(2026, 4, 23), fallback_days=7)


def test_get_rate_case_insensitive_code(usd):
    _mkrate(usd, date(2026, 4, 24), 12015.96)
    rate = get_rate_for("usd", date(2026, 4, 24))
    assert rate.currency_id == usd.id


def test_get_rate_unknown_currency():
    with pytest.raises(ValidationError):
        get_rate_for("XYZ", date(2026, 4, 24))


def test_get_latest_rate(usd):
    _mkrate(usd, date(2026, 4, 20), 12000)
    _mkrate(usd, date(2026, 4, 22), 12100)
    _mkrate(usd, date(2026, 4, 24), 12015.96)
    rate = get_latest_rate("USD")
    assert rate.date == date(2026, 4, 24)


def test_get_latest_rate_none_when_no_rates(usd):
    assert get_latest_rate("USD") is None
