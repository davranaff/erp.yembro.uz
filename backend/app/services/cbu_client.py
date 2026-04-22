"""Thin HTTP client for cbu.uz — Central Bank of Uzbekistan official rates.

Two endpoints are used:

* ``https://cbu.uz/ru/arkhiv-kursov-valyut/json/`` — latest rates for
  every currency the bank quotes.
* ``https://cbu.uz/ru/arkhiv-kursov-valyut/json/{CODE}/`` — latest rate
  for a single currency.

Both return a JSON array. Each element looks like::

    {
      "id": 69,
      "Code": "840",
      "Ccy": "USD",
      "CcyNm_RU": "Доллар США",
      "CcyNm_UZ": "AQSH dollari",
      "CcyNm_UZC": "АҚШ доллари",
      "CcyNm_EN": "US Dollar",
      "Nominal": "1",
      "Rate": "12834.47",
      "Diff": "-3.65",
      "Date": "23.04.2026"
    }

We normalize that into :class:`CBURate` with a :class:`~datetime.date`
and :class:`~decimal.Decimal` for easy downstream handling. ``Rate`` is
already the ``Nominal`` → base-currency price, so ``exchange_rate_to_base
= Rate / Nominal`` (Nominal is usually ``1``; for e.g. JPY it's ``100``).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable

import httpx


logger = logging.getLogger(__name__)


CBU_BASE_URL = "https://cbu.uz/ru/arkhiv-kursov-valyut/json"
DEFAULT_TIMEOUT_SECONDS = 15.0


@dataclass(slots=True, frozen=True)
class CBURate:
    """A single currency quote from the CBU archive."""

    code: str
    rate: Decimal
    rate_date: date
    nominal: Decimal
    name_ru: str | None = None

    @property
    def rate_to_base(self) -> Decimal:
        """Price of one foreign-currency unit in the base currency (UZS)."""

        if self.nominal == 0:
            return self.rate
        return (self.rate / self.nominal).quantize(Decimal("0.000001"))


def _parse_date(raw: str) -> date:
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("CBU response has empty Date")
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"CBU response has unrecognized Date: {raw!r}")


def _parse_decimal(raw: object, *, field: str) -> Decimal:
    if raw is None:
        raise ValueError(f"CBU response has missing {field}")
    try:
        return Decimal(str(raw).strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"CBU response has invalid {field}: {raw!r}") from exc


def _row_to_rate(row: dict) -> CBURate:
    code = str(row.get("Ccy") or "").strip().upper()
    if not code:
        raise ValueError("CBU response row is missing Ccy")
    return CBURate(
        code=code,
        rate=_parse_decimal(row.get("Rate"), field="Rate"),
        nominal=_parse_decimal(row.get("Nominal") or 1, field="Nominal"),
        rate_date=_parse_date(str(row.get("Date") or "")),
        name_ru=(row.get("CcyNm_RU") or None),
    )


class CBUClient:
    """Async client for cbu.uz rates endpoint."""

    def __init__(
        self,
        *,
        base_url: str = CBU_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._external_client = client

    async def _request(self, url: str) -> list[dict]:
        owned_client = self._external_client is None
        client = self._external_client or httpx.AsyncClient(timeout=self._timeout)
        try:
            response = await client.get(url)
            response.raise_for_status()
            payload = response.json()
        finally:
            if owned_client:
                await client.aclose()

        if not isinstance(payload, list):
            raise ValueError(
                f"CBU response is not a list: {type(payload).__name__}"
            )
        return payload

    async def fetch_all(self) -> list[CBURate]:
        """Fetch the latest rate for every currency in the CBU catalog."""

        rows = await self._request(f"{self._base_url}/")
        return [_row_to_rate(row) for row in rows]

    async def fetch_one(self, code: str) -> CBURate | None:
        """Fetch the latest rate for a single currency code (e.g. ``USD``)."""

        code_norm = code.strip().upper()
        if not code_norm:
            raise ValueError("Currency code is required")
        rows = await self._request(f"{self._base_url}/{code_norm}/")
        if not rows:
            return None
        return _row_to_rate(rows[0])

    async def fetch_for_codes(self, codes: Iterable[str]) -> list[CBURate]:
        """Fetch a subset of currencies in one round-trip.

        ``fetch_all()`` then filtered — still one HTTP call, cheaper
        than looping per-code.
        """

        wanted = {c.strip().upper() for c in codes if c and c.strip()}
        if not wanted:
            return []
        all_rates = await self.fetch_all()
        return [r for r in all_rates if r.code in wanted]
