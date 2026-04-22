"""Unit tests for ``resolve_exchange_rate`` — exchange-rate lookup logic.

The resolver is the piece of code every finance/inventory module will
call when saving a transaction to stamp the historically-correct
``exchange_rate_to_base`` onto the row. The tests below verify the
three branches:

1. the currency is the base (default) → rate is always ``1``;
2. a history row exists with ``rate_date <= on_date`` → use it;
3. no history row at all → fall back to the catalog's
   ``exchange_rate_to_base``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable

import pytest

from app.services.exchange_rate import resolve_exchange_rate


class _FakeDb:
    """Tiny in-memory stand-in for ``app.db.pool.Database``.

    Keeps a list of currency rows and a list of history rows, then
    answers the two queries the resolver emits.
    """

    def __init__(
        self,
        *,
        currencies: list[dict[str, Any]],
        history: list[dict[str, Any]] | None = None,
    ) -> None:
        self._currencies = currencies
        self._history = history or []

    async def fetchrow(self, query: str, *args: Any) -> dict[str, Any] | None:
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT id, organization_id, code"):
            currency_id, organization_id = args
            for row in self._currencies:
                if row["id"] == currency_id and row["organization_id"] == organization_id:
                    return row
            return None
        if "FROM currency_exchange_rates" in normalized:
            organization_id, currency_id, on_date = args
            eligible = [
                r
                for r in self._history
                if r["organization_id"] == organization_id
                and r["currency_id"] == currency_id
                and r["rate_date"] <= on_date
            ]
            if not eligible:
                return None
            eligible.sort(key=lambda r: r["rate_date"], reverse=True)
            return eligible[0]
        raise AssertionError(f"Unexpected query: {query!r}")

    async def fetch(self, query: str, *args: Any) -> Iterable[dict[str, Any]]:
        raise AssertionError("fetch() should not be called by the resolver")


@pytest.mark.asyncio
async def test_resolver_returns_one_for_default_currency() -> None:
    db = _FakeDb(
        currencies=[
            {
                "id": "cur-uzs",
                "organization_id": "org-1",
                "code": "UZS",
                "is_default": True,
                "exchange_rate_to_base": Decimal("1"),
            }
        ]
    )

    resolved = await resolve_exchange_rate(
        db,  # type: ignore[arg-type]
        organization_id="org-1",
        currency_id="cur-uzs",
        on_date=date(2026, 4, 23),
    )

    assert resolved.is_base is True
    assert resolved.rate == Decimal("1")
    assert resolved.source == "base"
    assert resolved.currency_code == "UZS"


@pytest.mark.asyncio
async def test_resolver_picks_history_on_exact_date() -> None:
    db = _FakeDb(
        currencies=[
            {
                "id": "cur-usd",
                "organization_id": "org-1",
                "code": "USD",
                "is_default": False,
                "exchange_rate_to_base": Decimal("10000"),
            }
        ],
        history=[
            {
                "organization_id": "org-1",
                "currency_id": "cur-usd",
                "rate_date": date(2026, 4, 22),
                "rate": Decimal("12800.00"),
            },
            {
                "organization_id": "org-1",
                "currency_id": "cur-usd",
                "rate_date": date(2026, 4, 23),
                "rate": Decimal("12834.47"),
            },
        ],
    )

    resolved = await resolve_exchange_rate(
        db,  # type: ignore[arg-type]
        organization_id="org-1",
        currency_id="cur-usd",
        on_date=date(2026, 4, 23),
    )

    assert resolved.is_base is False
    assert resolved.rate == Decimal("12834.47")
    assert resolved.rate_date == date(2026, 4, 23)
    assert resolved.source == "history"


@pytest.mark.asyncio
async def test_resolver_uses_latest_before_date_when_exact_missing() -> None:
    """Weekend holes: April 25 (Saturday) has no CBU row → use Friday."""

    db = _FakeDb(
        currencies=[
            {
                "id": "cur-usd",
                "organization_id": "org-1",
                "code": "USD",
                "is_default": False,
                "exchange_rate_to_base": Decimal("10000"),
            }
        ],
        history=[
            {
                "organization_id": "org-1",
                "currency_id": "cur-usd",
                "rate_date": date(2026, 4, 23),
                "rate": Decimal("12834.47"),
            },
            {
                "organization_id": "org-1",
                "currency_id": "cur-usd",
                "rate_date": date(2026, 4, 24),
                "rate": Decimal("12840.00"),
            },
        ],
    )

    resolved = await resolve_exchange_rate(
        db,  # type: ignore[arg-type]
        organization_id="org-1",
        currency_id="cur-usd",
        on_date=date(2026, 4, 25),
    )

    assert resolved.rate == Decimal("12840.00")
    assert resolved.rate_date == date(2026, 4, 24)


@pytest.mark.asyncio
async def test_resolver_falls_back_to_catalog_rate() -> None:
    db = _FakeDb(
        currencies=[
            {
                "id": "cur-usd",
                "organization_id": "org-1",
                "code": "USD",
                "is_default": False,
                "exchange_rate_to_base": Decimal("12000"),
            }
        ],
    )

    resolved = await resolve_exchange_rate(
        db,  # type: ignore[arg-type]
        organization_id="org-1",
        currency_id="cur-usd",
        on_date=date(2026, 4, 23),
    )

    assert resolved.rate == Decimal("12000")
    assert resolved.rate_date is None
    assert resolved.source == "catalog"
