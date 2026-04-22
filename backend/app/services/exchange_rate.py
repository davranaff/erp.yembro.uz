"""Currency exchange rate service.

This module does three things:

1. Persists a history of ``(organization_id, currency_id, rate_date)
   → rate`` snapshots in ``currency_exchange_rates``.
2. Resolves the correct ``exchange_rate_to_base`` for any business
   operation — when a cash transaction / debt payment / arrival / etc.
   is created, we look up the most recent rate on or before the
   transaction date so that the historical snapshot is faithful even
   if someone edits the row later.
3. Syncs the latest quotes from the Central Bank of Uzbekistan
   (``cbu.uz``) into the table. The sync is idempotent via the
   ``(organization_id, currency_id, rate_date)`` unique constraint.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Iterable, Mapping
from uuid import UUID

from app.core.exceptions import NotFoundError, ValidationError
from app.db.pool import Database
from app.repositories.core import CurrencyExchangeRateRepository
from app.schemas.core import CurrencyExchangeRateReadSchema
from app.services.base import BaseService
from app.services.cbu_client import CBUClient, CBURate

if TYPE_CHECKING:
    from app.api.deps import CurrentActor


logger = logging.getLogger(__name__)


SOURCE_CBU = "cbu"
SOURCE_MANUAL = "manual"
SOURCE_SEED = "seed"
ALLOWED_SOURCES = (SOURCE_CBU, SOURCE_MANUAL, SOURCE_SEED)


@dataclass(slots=True, frozen=True)
class ResolvedRate:
    """Result of resolving a rate for a business operation."""

    rate: Decimal
    rate_date: date | None
    currency_code: str
    source: str  # 'catalog' | 'history' | 'base'
    is_base: bool


async def _fetch_currency_row(
    db: Database,
    *,
    organization_id: str,
    currency_id: str,
) -> Mapping[str, Any]:
    row = await db.fetchrow(
        """
        SELECT id, organization_id, code, is_default, exchange_rate_to_base
        FROM currencies
        WHERE id = $1 AND organization_id = $2
        """,
        currency_id,
        organization_id,
    )
    if row is None:
        raise NotFoundError(f"currency {currency_id} not found")
    return dict(row)


async def _fetch_currencies_by_code(
    db: Database,
    *,
    organization_id: str,
) -> dict[str, Mapping[str, Any]]:
    rows = await db.fetch(
        """
        SELECT id, code, is_default
        FROM currencies
        WHERE organization_id = $1 AND is_active = true
        """,
        organization_id,
    )
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        code = str(row["code"] or "").strip().upper()
        if code:
            result[code] = dict(row)
    return result


async def resolve_exchange_rate(
    db: Database,
    *,
    organization_id: str | UUID,
    currency_id: str | UUID,
    on_date: date,
) -> ResolvedRate:
    """Resolve the historical rate for a transaction on ``on_date``.

    Algorithm:

    1. If the currency is the organization's default (base) currency →
       return ``1.0``.
    2. Otherwise look up the most recent row in
       ``currency_exchange_rates`` with
       ``rate_date <= on_date`` (typically *exactly* ``on_date``, but
       we fall back to the latest known rate if the CBU sync missed a
       day — e.g. weekends).
    3. If no history row exists at all, fall back to
       ``currencies.exchange_rate_to_base`` as a last resort.
    """

    organization_id_str = str(organization_id)
    currency_id_str = str(currency_id)

    currency = await _fetch_currency_row(
        db,
        organization_id=organization_id_str,
        currency_id=currency_id_str,
    )
    if currency.get("is_default"):
        return ResolvedRate(
            rate=Decimal("1"),
            rate_date=on_date,
            currency_code=str(currency.get("code") or ""),
            source="base",
            is_base=True,
        )

    history_row = await db.fetchrow(
        """
        SELECT rate, rate_date
        FROM currency_exchange_rates
        WHERE organization_id = $1
          AND currency_id = $2
          AND rate_date <= $3
        ORDER BY rate_date DESC
        LIMIT 1
        """,
        organization_id_str,
        currency_id_str,
        on_date,
    )
    if history_row is not None:
        rate_raw = history_row["rate"]
        return ResolvedRate(
            rate=Decimal(str(rate_raw)),
            rate_date=history_row["rate_date"],
            currency_code=str(currency.get("code") or ""),
            source="history",
            is_base=False,
        )

    fallback_rate_raw = currency.get("exchange_rate_to_base")
    fallback_rate = (
        Decimal(str(fallback_rate_raw)) if fallback_rate_raw is not None else Decimal("1")
    )
    return ResolvedRate(
        rate=fallback_rate,
        rate_date=None,
        currency_code=str(currency.get("code") or ""),
        source="catalog",
        is_base=False,
    )


class CurrencyExchangeRateService(BaseService):
    """CRUD + sync service for the exchange rate history table."""

    read_schema = CurrencyExchangeRateReadSchema

    def __init__(
        self,
        repository: CurrencyExchangeRateRepository,
        *,
        cbu_client: CBUClient | None = None,
    ) -> None:
        super().__init__(repository=repository)
        self._cbu_client = cbu_client or CBUClient()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _normalize_source(self, raw: Any) -> str:
        value = str(raw or SOURCE_MANUAL).strip().lower()
        if value not in ALLOWED_SOURCES:
            raise ValidationError(
                "source must be one of: " + ", ".join(ALLOWED_SOURCES)
            )
        return value

    async def _before_create(
        self,
        data: dict[str, Any],
        *,
        actor: "CurrentActor | None" = None,
    ) -> dict[str, Any]:
        if "source" in data:
            data["source"] = self._normalize_source(data.get("source"))
        else:
            data["source"] = SOURCE_MANUAL

        rate_raw = data.get("rate")
        if rate_raw is None:
            raise ValidationError("rate is required")
        try:
            rate = Decimal(str(rate_raw))
        except Exception as exc:  # noqa: BLE001
            raise ValidationError("rate must be a number") from exc
        if rate <= 0:
            raise ValidationError("rate must be positive")
        data["rate"] = str(rate)
        return data

    # ------------------------------------------------------------------
    # Read helpers used by API endpoints
    # ------------------------------------------------------------------

    async def get_latest_for_currency(
        self,
        *,
        organization_id: str,
        currency_id: str,
    ) -> Mapping[str, Any] | None:
        row = await self.repository.db.fetchrow(
            """
            SELECT *
            FROM currency_exchange_rates
            WHERE organization_id = $1 AND currency_id = $2
            ORDER BY rate_date DESC
            LIMIT 1
            """,
            organization_id,
            currency_id,
        )
        return dict(row) if row else None

    async def list_history(
        self,
        *,
        organization_id: str,
        currency_id: str | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Mapping[str, Any]], int]:
        conditions = ["organization_id = $1"]
        params: list[Any] = [organization_id]
        if currency_id:
            params.append(currency_id)
            conditions.append(f"currency_id = ${len(params)}")
        if date_from:
            params.append(date_from)
            conditions.append(f"rate_date >= ${len(params)}")
        if date_to:
            params.append(date_to)
            conditions.append(f"rate_date <= ${len(params)}")
        where_clause = " AND ".join(conditions)

        total_row = await self.repository.db.fetchrow(
            f"SELECT COUNT(*) AS total FROM currency_exchange_rates WHERE {where_clause}",
            *params,
        )
        total = int(total_row["total"]) if total_row else 0

        params_with_pagination = [*params, limit, offset]
        rows = await self.repository.db.fetch(
            f"""
            SELECT *
            FROM currency_exchange_rates
            WHERE {where_clause}
            ORDER BY rate_date DESC, created_at DESC
            LIMIT ${len(params_with_pagination) - 1}
            OFFSET ${len(params_with_pagination)}
            """,
            *params_with_pagination,
        )
        return [dict(row) for row in rows], total

    # ------------------------------------------------------------------
    # Upsert & CBU sync
    # ------------------------------------------------------------------

    async def upsert_rate(
        self,
        *,
        organization_id: str,
        currency_id: str,
        rate_date: date,
        rate: Decimal,
        source: str = SOURCE_CBU,
        source_ref: str | None = None,
    ) -> Mapping[str, Any]:
        source_norm = self._normalize_source(source)
        if rate <= 0:
            raise ValidationError("rate must be positive")

        row = await self.repository.db.fetchrow(
            """
            INSERT INTO currency_exchange_rates (
                id, organization_id, currency_id, rate_date, rate, source,
                source_ref, created_at, updated_at
            )
            VALUES (
                gen_random_uuid(), $1, $2, $3, $4, $5, $6, NOW(), NOW()
            )
            ON CONFLICT (organization_id, currency_id, rate_date) DO UPDATE SET
                rate = EXCLUDED.rate,
                source = EXCLUDED.source,
                source_ref = EXCLUDED.source_ref,
                updated_at = NOW()
            RETURNING *
            """,
            organization_id,
            currency_id,
            rate_date,
            str(rate),
            source_norm,
            source_ref,
        )
        return dict(row) if row else {}

    async def sync_from_cbu(
        self,
        *,
        organization_id: str,
        codes: Iterable[str] | None = None,
    ) -> dict[str, Any]:
        """Pull latest CBU rates and upsert them for this organization.

        Only currencies that actually exist in the organization's
        ``currencies`` catalog are touched — CBU publishes ~20
        currencies but an org usually cares about a handful (UZS, USD,
        EUR, RUB, …).
        """

        org_currencies = await _fetch_currencies_by_code(
            self.repository.db, organization_id=organization_id
        )
        if not org_currencies:
            return {"inserted": 0, "updated": 0, "skipped": 0, "rates": []}

        foreign_codes = [code for code, row in org_currencies.items() if not row.get("is_default")]
        if codes:
            wanted = {c.strip().upper() for c in codes if c and c.strip()}
            foreign_codes = [c for c in foreign_codes if c in wanted]
        if not foreign_codes:
            return {"inserted": 0, "updated": 0, "skipped": 0, "rates": []}

        try:
            cbu_rates = await self._cbu_client.fetch_for_codes(foreign_codes)
        except Exception as exc:  # noqa: BLE001
            logger.exception("CBU rates fetch failed: %s", exc)
            raise ValidationError(f"CBU fetch failed: {exc}")

        saved: list[dict[str, Any]] = []
        for cbu_rate in cbu_rates:
            catalog_row = org_currencies.get(cbu_rate.code)
            if not catalog_row:
                continue
            saved_row = await self.upsert_rate(
                organization_id=organization_id,
                currency_id=str(catalog_row["id"]),
                rate_date=cbu_rate.rate_date,
                rate=cbu_rate.rate_to_base,
                source=SOURCE_CBU,
                source_ref=f"cbu:{cbu_rate.code}",
            )
            saved.append(
                {
                    "currency_id": str(saved_row.get("currency_id")),
                    "currency_code": cbu_rate.code,
                    "rate_date": cbu_rate.rate_date.isoformat(),
                    "rate": str(saved_row.get("rate")),
                }
            )

        return {
            "inserted": len(saved),
            "updated": 0,
            "skipped": len(foreign_codes) - len(saved),
            "rates": saved,
        }

    async def sync_all_organizations(
        self,
    ) -> list[dict[str, Any]]:
        """Run :meth:`sync_from_cbu` for every organization in the system.

        Used by the periodic Taskiq scheduler. Failures are logged per
        org and don't abort the loop.
        """

        org_rows = await self.repository.db.fetch(
            "SELECT id FROM organizations WHERE is_active = true"
        )
        results: list[dict[str, Any]] = []
        for row in org_rows:
            org_id = str(row["id"])
            try:
                summary = await self.sync_from_cbu(organization_id=org_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("CBU sync failed for org %s: %s", org_id, exc)
                results.append({"organization_id": org_id, "error": str(exc)})
                continue
            results.append({"organization_id": org_id, **summary})
        return results


__all__ = [
    "CurrencyExchangeRateService",
    "ResolvedRate",
    "resolve_exchange_rate",
    "SOURCE_CBU",
    "SOURCE_MANUAL",
    "SOURCE_SEED",
]
