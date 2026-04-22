"""Unit tests for the CBU.uz client and its parsing helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.services.cbu_client import CBUClient, CBURate, _row_to_rate


def test_row_to_rate_parses_dotted_date() -> None:
    rate = _row_to_rate(
        {
            "Ccy": "USD",
            "Rate": "12834.47",
            "Nominal": "1",
            "Date": "23.04.2026",
            "CcyNm_RU": "Доллар США",
        }
    )
    assert rate.code == "USD"
    assert rate.rate == Decimal("12834.47")
    assert rate.nominal == Decimal("1")
    assert rate.rate_date == date(2026, 4, 23)
    assert rate.name_ru == "Доллар США"


def test_row_to_rate_parses_iso_date() -> None:
    rate = _row_to_rate(
        {"Ccy": "EUR", "Rate": "14010.12", "Nominal": 1, "Date": "2026-04-23"}
    )
    assert rate.rate_date == date(2026, 4, 23)


def test_rate_to_base_respects_nominal() -> None:
    # JPY is quoted per 100 units in many central bank feeds.
    rate = CBURate(
        code="JPY",
        rate=Decimal("8300"),
        nominal=Decimal("100"),
        rate_date=date(2026, 4, 23),
    )
    assert rate.rate_to_base == Decimal("83.000000")


def test_rate_to_base_with_unit_nominal() -> None:
    rate = CBURate(
        code="USD",
        rate=Decimal("12834.47"),
        nominal=Decimal("1"),
        rate_date=date(2026, 4, 23),
    )
    assert rate.rate_to_base == Decimal("12834.470000")


def test_row_to_rate_requires_code() -> None:
    with pytest.raises(ValueError):
        _row_to_rate({"Rate": "1", "Nominal": "1", "Date": "23.04.2026"})


def test_row_to_rate_rejects_bad_date() -> None:
    with pytest.raises(ValueError):
        _row_to_rate({"Ccy": "USD", "Rate": "1", "Nominal": "1", "Date": "tomorrow"})


@pytest.mark.asyncio
async def test_fetch_all_parses_list() -> None:
    # Use httpx's MockTransport so we never touch the real network.
    payload = [
        {
            "Ccy": "USD",
            "Rate": "12834.47",
            "Nominal": "1",
            "Date": "23.04.2026",
            "CcyNm_RU": "Доллар США",
        },
        {
            "Ccy": "EUR",
            "Rate": "14010.12",
            "Nominal": "1",
            "Date": "23.04.2026",
            "CcyNm_RU": "Евро",
        },
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/json/")
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CBUClient(client=http_client)
        rates = await client.fetch_all()

    assert [r.code for r in rates] == ["USD", "EUR"]
    assert rates[0].rate == Decimal("12834.47")


@pytest.mark.asyncio
async def test_fetch_for_codes_filters_catalog() -> None:
    payload = [
        {"Ccy": "USD", "Rate": "12834", "Nominal": "1", "Date": "23.04.2026"},
        {"Ccy": "EUR", "Rate": "14010", "Nominal": "1", "Date": "23.04.2026"},
        {"Ccy": "RUB", "Rate": "140", "Nominal": "1", "Date": "23.04.2026"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CBUClient(client=http_client)
        rates = await client.fetch_for_codes(["usd", "RUB", "XYZ"])

    codes = {r.code for r in rates}
    assert codes == {"USD", "RUB"}


@pytest.mark.asyncio
async def test_fetch_one_returns_none_when_empty() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[])

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = CBUClient(client=http_client)
        assert await client.fetch_one("USD") is None
