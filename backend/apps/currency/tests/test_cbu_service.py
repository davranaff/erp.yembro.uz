"""
Тесты CBU-сервиса: парсер, upsert, идемпотентность.
"""
from datetime import date
from decimal import Decimal

import pytest
import responses

from apps.currency.models import Currency, ExchangeRate
from apps.currency.services.cbu import (
    CBUFetchError,
    build_cbu_url,
    fetch_rates_from_cbu,
    sync_cbu_rates,
    upsert_rates,
)


pytestmark = pytest.mark.django_db


SAMPLE_PAYLOAD = [
    {
        "id": 68,
        "Code": "840",
        "Ccy": "USD",
        "CcyNm_RU": "Доллар США",
        "CcyNm_EN": "US Dollar",
        "Nominal": "1",
        "Rate": "12015.96",
        "Diff": "-26.53",
        "Date": "24.04.2026",
    },
    {
        "id": 21,
        "Code": "978",
        "Ccy": "EUR",
        "CcyNm_RU": "Евро",
        "CcyNm_EN": "Euro",
        "Nominal": "1",
        "Rate": "13750.12",
        "Diff": "-5.11",
        "Date": "24.04.2026",
    },
]


def test_build_url_no_args():
    assert build_cbu_url() == "https://cbu.uz/ru/arkhiv-kursov-valyut/json/"


def test_build_url_with_code_and_date():
    url = build_cbu_url(currency_code="usd", on_date=date(2026, 4, 24))
    assert url == "https://cbu.uz/ru/arkhiv-kursov-valyut/json/USD/2026-04-24/"


def test_upsert_creates_currencies_and_rates():
    # seed миграции create UZS и USD заранее (currency/0003_seed_base_currencies).
    # Payload содержит USD (уже есть) + EUR (новая) → created rate = 2, но
    # currencies_created = 1 (только EUR).
    usd_existed = Currency.objects.filter(code="USD").exists()
    eur_existed = Currency.objects.filter(code="EUR").exists()
    expected_new_currencies = (0 if usd_existed else 1) + (0 if eur_existed else 1)

    currencies_before = Currency.objects.count()
    rates_before = ExchangeRate.objects.count()

    result = upsert_rates(SAMPLE_PAYLOAD)

    assert result.fetched == 2
    assert result.created == 2
    assert result.updated == 0
    assert result.currencies_created == expected_new_currencies

    assert Currency.objects.count() == currencies_before + expected_new_currencies
    assert ExchangeRate.objects.count() == rates_before + 2

    usd = Currency.objects.get(code="USD")
    assert usd.numeric_code == "840"
    assert usd.name_ru == "Доллар США"

    rate = ExchangeRate.objects.get(currency=usd, date=date(2026, 4, 24))
    assert rate.rate == Decimal("12015.96")
    assert rate.nominal == 1
    assert rate.source == "cbu.uz"


def test_upsert_is_idempotent():
    upsert_rates(SAMPLE_PAYLOAD)
    currencies_after_first = Currency.objects.count()
    rates_after_first = ExchangeRate.objects.count()

    result = upsert_rates(SAMPLE_PAYLOAD)

    assert result.created == 0
    assert result.updated == 2
    assert result.currencies_created == 0
    assert Currency.objects.count() == currencies_after_first
    assert ExchangeRate.objects.count() == rates_after_first


def test_upsert_skips_malformed_row():
    bad = [{"Ccy": "USD", "Date": "not-a-date", "Rate": "1"}]
    result = upsert_rates(bad)
    assert result.skipped == 1
    assert result.created == 0


@responses.activate
def test_fetch_rates_200_ok():
    responses.add(
        responses.GET,
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/",
        json=SAMPLE_PAYLOAD,
        status=200,
    )
    rows = fetch_rates_from_cbu()
    assert len(rows) == 2
    assert rows[0]["Ccy"] == "USD"


@responses.activate
def test_fetch_rates_raises_on_http_error():
    responses.add(
        responses.GET,
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/",
        status=500,
        body="oops",
    )
    with pytest.raises(CBUFetchError):
        fetch_rates_from_cbu()


@responses.activate
def test_fetch_rates_raises_on_non_json():
    responses.add(
        responses.GET,
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/",
        status=200,
        body="not json",
    )
    with pytest.raises(CBUFetchError):
        fetch_rates_from_cbu()


@responses.activate
def test_sync_cbu_rates_end_to_end():
    responses.add(
        responses.GET,
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/",
        json=SAMPLE_PAYLOAD,
        status=200,
    )
    result = sync_cbu_rates()
    assert result.fetched == 2
    assert result.created == 2


@responses.activate
def test_sync_cbu_rates_with_specific_currency_and_date():
    responses.add(
        responses.GET,
        "https://cbu.uz/ru/arkhiv-kursov-valyut/json/USD/2026-04-24/",
        json=[SAMPLE_PAYLOAD[0]],
        status=200,
    )
    result = sync_cbu_rates(currency_code="USD", on_date=date(2026, 4, 24))
    assert result.fetched == 1
    assert result.created == 1
