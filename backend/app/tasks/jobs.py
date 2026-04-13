from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.db.pool import Database
from app.repositories.egg import EggMonthlyAnalyticsRepository
from app.repositories.incubation import FactoryMonthlyAnalyticsRepository, IncubationMonthlyAnalyticsRepository
from app.taskiq_app import broker


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _next_month_start(value: date) -> date:
    if value.month == 12:
        return date(value.year + 1, 1, 1)
    return date(value.year, value.month + 1, 1)


def _recent_month_starts(today: date) -> list[date]:
    current = _month_start(today)
    if current.month == 1:
        previous = date(current.year - 1, 12, 1)
    else:
        previous = date(current.year, current.month - 1, 1)
    return [previous, current]


async def _upsert_egg_monthly_analytics(db: Database, *, start: date, end: date) -> int:
    repository = EggMonthlyAnalyticsRepository(db)

    production_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            COALESCE(SUM(eggs_collected), 0) AS produced_count,
            COALESCE(SUM(eggs_broken), 0) AS broken_count,
            COALESCE(SUM(eggs_rejected), 0) AS rejected_count
        FROM egg_production
        WHERE produced_on >= $1
          AND produced_on < $2
        GROUP BY organization_id, department_id
        """,
        start,
        end,
    )
    shipment_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            COALESCE(SUM(eggs_count), 0) AS shipped_count,
            COALESCE(SUM(COALESCE(unit_price, 0) * eggs_count), 0) AS revenue,
            MAX(currency) AS currency
        FROM egg_shipments
        WHERE shipped_on >= $1
          AND shipped_on < $2
        GROUP BY organization_id, department_id
        """,
        start,
        end,
    )

    merged: dict[tuple[str, str | None], dict[str, object]] = {}

    for row in production_rows:
        key = (str(row["organization_id"]), str(row["department_id"]) if row["department_id"] is not None else None)
        merged[key] = {
            "organization_id": key[0],
            "department_id": key[1],
            "produced_count": int(row["produced_count"] or 0),
            "broken_count": int(row["broken_count"] or 0),
            "rejected_count": int(row["rejected_count"] or 0),
            "shipped_count": 0,
            "revenue": Decimal("0"),
            "currency": None,
        }

    for row in shipment_rows:
        key = (str(row["organization_id"]), str(row["department_id"]) if row["department_id"] is not None else None)
        entry = merged.setdefault(
            key,
            {
                "organization_id": key[0],
                "department_id": key[1],
                "produced_count": 0,
                "broken_count": 0,
                "rejected_count": 0,
                "shipped_count": 0,
                "revenue": Decimal("0"),
                "currency": None,
            },
        )
        entry["shipped_count"] = int(row["shipped_count"] or 0)
        entry["revenue"] = Decimal(str(row["revenue"] or 0)).quantize(Decimal("0.01"))
        entry["currency"] = str(row["currency"]) if row["currency"] is not None else None

    upserted = 0
    for entry in merged.values():
        payload = {
            "id": str(uuid4()),
            "organization_id": entry["organization_id"],
            "department_id": entry["department_id"],
            "month_start": start,
            "produced_count": entry["produced_count"],
            "broken_count": entry["broken_count"],
            "shipped_count": entry["shipped_count"],
            "rejected_count": entry["rejected_count"],
            "revenue": entry["revenue"],
            "currency": entry["currency"] or "UZS",
        }
        await repository.upsert(
            payload=payload,
            conflict_columns=["organization_id", "department_id", "month_start"],
            update_columns=[
                "produced_count",
                "broken_count",
                "shipped_count",
                "rejected_count",
                "revenue",
                "currency",
            ],
        )
        upserted += 1

    return upserted


async def _upsert_incubation_monthly_analytics(db: Database, *, start: date, end: date) -> int:
    repository = IncubationMonthlyAnalyticsRepository(db)

    arrived_rows = await db.fetch(
        """
        SELECT organization_id, department_id, COALESCE(SUM(eggs_arrived), 0) AS eggs_arrived
        FROM incubation_batches
        WHERE arrived_on >= $1
          AND arrived_on < $2
        GROUP BY organization_id, department_id
        """,
        start,
        end,
    )
    run_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            COALESCE(SUM(grade_1_count), 0) AS grade1_count,
            COALESCE(SUM(grade_2_count), 0) AS grade2_count,
            COALESCE(SUM(bad_eggs_count), 0) AS bad_eggs_count,
            COALESCE(SUM(chicks_hatched), 0) AS chicks_hatched
        FROM incubation_runs
        WHERE COALESCE(end_date, start_date) >= $1
          AND COALESCE(end_date, start_date) < $2
        GROUP BY organization_id, department_id
        """,
        start,
        end,
    )
    shipped_rows = await db.fetch(
        """
        SELECT organization_id, department_id, COALESCE(SUM(chicks_count), 0) AS chicks_shipped
        FROM chick_shipments
        WHERE shipped_on >= $1
          AND shipped_on < $2
        GROUP BY organization_id, department_id
        """,
        start,
        end,
    )

    merged: dict[tuple[str, str | None], dict[str, int]] = defaultdict(
        lambda: {
            "eggs_arrived": 0,
            "grade1_count": 0,
            "grade2_count": 0,
            "bad_eggs_count": 0,
            "chicks_hatched": 0,
            "chicks_shipped": 0,
        }
    )

    for row in arrived_rows:
        key = (str(row["organization_id"]), str(row["department_id"]) if row["department_id"] is not None else None)
        merged[key]["eggs_arrived"] = int(row["eggs_arrived"] or 0)

    for row in run_rows:
        key = (str(row["organization_id"]), str(row["department_id"]) if row["department_id"] is not None else None)
        merged[key]["grade1_count"] = int(row["grade1_count"] or 0)
        merged[key]["grade2_count"] = int(row["grade2_count"] or 0)
        merged[key]["bad_eggs_count"] = int(row["bad_eggs_count"] or 0)
        merged[key]["chicks_hatched"] = int(row["chicks_hatched"] or 0)

    for row in shipped_rows:
        key = (str(row["organization_id"]), str(row["department_id"]) if row["department_id"] is not None else None)
        merged[key]["chicks_shipped"] = int(row["chicks_shipped"] or 0)

    upserted = 0
    for (organization_id, department_id), metrics in merged.items():
        payload = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "department_id": department_id,
            "month_start": start,
            **metrics,
        }
        await repository.upsert(
            payload=payload,
            conflict_columns=["organization_id", "department_id", "month_start"],
            update_columns=[
                "eggs_arrived",
                "grade1_count",
                "grade2_count",
                "bad_eggs_count",
                "chicks_hatched",
                "chicks_shipped",
            ],
        )
        upserted += 1

    return upserted


async def _upsert_factory_monthly_analytics(db: Database, *, start: date, end: date) -> int:
    repository = FactoryMonthlyAnalyticsRepository(db)

    chicks_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            poultry_type_id,
            COALESCE(SUM(chicks_count), 0) AS chicks_arrived
        FROM chick_arrivals
        WHERE arrived_on >= $1
          AND arrived_on < $2
        GROUP BY organization_id, department_id, poultry_type_id
        """,
        start,
        end,
    )
    feed_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            poultry_type_id,
            COALESCE(SUM(quantity), 0) AS feed_quantity
        FROM feed_consumptions
        WHERE consumed_on >= $1
          AND consumed_on < $2
        GROUP BY organization_id, department_id, poultry_type_id
        """,
        start,
        end,
    )
    medicine_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            poultry_type_id,
            COALESCE(SUM(quantity), 0) AS medicines_arrived
        FROM medicine_arrivals
        WHERE arrived_on >= $1
          AND arrived_on < $2
        GROUP BY organization_id, department_id, poultry_type_id
        """,
        start,
        end,
    )

    merged: dict[tuple[str, str | None, str | None], dict[str, object]] = defaultdict(
        lambda: {
            "chicks_arrived": 0,
            "feed_quantity": Decimal("0.000"),
            "feed_quantity_unit": "kg",
            "medicines_arrived": Decimal("0.000"),
            "note": None,
        }
    )

    for row in chicks_rows:
        key = (
            str(row["organization_id"]),
            str(row["department_id"]) if row["department_id"] is not None else None,
            str(row["poultry_type_id"]) if row["poultry_type_id"] is not None else None,
        )
        merged[key]["chicks_arrived"] = int(row["chicks_arrived"] or 0)

    for row in feed_rows:
        key = (
            str(row["organization_id"]),
            str(row["department_id"]) if row["department_id"] is not None else None,
            str(row["poultry_type_id"]) if row["poultry_type_id"] is not None else None,
        )
        merged[key]["feed_quantity"] = Decimal(str(row["feed_quantity"] or 0)).quantize(Decimal("0.001"))

    for row in medicine_rows:
        key = (
            str(row["organization_id"]),
            str(row["department_id"]) if row["department_id"] is not None else None,
            str(row["poultry_type_id"]) if row["poultry_type_id"] is not None else None,
        )
        merged[key]["medicines_arrived"] = Decimal(str(row["medicines_arrived"] or 0)).quantize(Decimal("0.001"))

    upserted = 0
    for (organization_id, department_id, poultry_type_id), metrics in merged.items():
        payload = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "department_id": department_id,
            "poultry_type_id": poultry_type_id,
            "month_start": start,
            **metrics,
        }
        await repository.upsert(
            payload=payload,
            conflict_columns=["organization_id", "department_id", "poultry_type_id", "month_start"],
            update_columns=[
                "chicks_arrived",
                "feed_quantity",
                "feed_quantity_unit",
                "medicines_arrived",
                "note",
            ],
        )
        upserted += 1

    return upserted


async def refresh_monthly_analytics() -> dict[str, object]:
    settings = get_settings()
    db = Database(
        dsn=settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()

    try:
        refreshed: list[dict[str, object]] = []
        today = datetime.now(timezone.utc).date()
        for month_start in _recent_month_starts(today):
            month_end = _next_month_start(month_start)
            async with db.transaction():
                egg_count = await _upsert_egg_monthly_analytics(db, start=month_start, end=month_end)
                incubation_count = await _upsert_incubation_monthly_analytics(db, start=month_start, end=month_end)
                factory_count = await _upsert_factory_monthly_analytics(db, start=month_start, end=month_end)

            refreshed.append(
                {
                    "month_start": month_start.isoformat(),
                    "egg_rows": egg_count,
                    "incubation_rows": incubation_count,
                    "factory_rows": factory_count,
                }
            )

        return {
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
            "months": refreshed,
        }
    finally:
        await db.disconnect()


@broker.task(schedule=[{"cron": "*/5 * * * *", "schedule_id": "heartbeat"}])
async def heartbeat_task() -> dict[str, str]:
    return {"beat_at": datetime.now(timezone.utc).isoformat()}


@broker.task(schedule=[{"cron": "15 2 * * *", "schedule_id": "monthly-analytics-autofill"}])
async def monthly_analytics_autofill_task() -> dict[str, object]:
    return await refresh_monthly_analytics()
