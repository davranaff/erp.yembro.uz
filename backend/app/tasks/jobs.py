from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.core.config import get_settings
from app.db.pool import Database
from app.repositories.egg import EggMonthlyAnalyticsRepository
from app.repositories.feed import FeedMonthlyAnalyticsRepository
from app.repositories.incubation import FactoryMonthlyAnalyticsRepository, IncubationMonthlyAnalyticsRepository
from app.repositories.slaughter import SlaughterMonthlyAnalyticsRepository
from app.services.telegram_alerts import deliver_operational_admin_alert
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


async def _upsert_feed_monthly_analytics(db: Database, *, start: date, end: date) -> int:
    repository = FeedMonthlyAnalyticsRepository(db)

    arrival_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            feed_type_id,
            COALESCE(SUM(quantity), 0) AS raw_arrivals_kg,
            COALESCE(SUM(COALESCE(unit_price, 0) * quantity), 0) AS purchased_amount,
            MAX(currency) AS currency
        FROM feed_arrivals
        WHERE arrived_on >= $1
          AND arrived_on < $2
        GROUP BY organization_id, department_id, feed_type_id
        """,
        start,
        end,
    )
    consumption_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            feed_type_id,
            COALESCE(SUM(quantity), 0) AS raw_consumptions_kg
        FROM feed_consumptions
        WHERE consumed_on >= $1
          AND consumed_on < $2
        GROUP BY organization_id, department_id, feed_type_id
        """,
        start,
        end,
    )
    production_rows = await db.fetch(
        """
        SELECT
            pb.organization_id,
            pb.department_id,
            f.feed_type_id,
            COALESCE(SUM(pb.actual_output), 0) AS produced_kg
        FROM feed_production_batches AS pb
        JOIN feed_formulas AS f ON f.id = pb.formula_id
        WHERE COALESCE(pb.finished_on, pb.started_on) >= $1
          AND COALESCE(pb.finished_on, pb.started_on) < $2
        GROUP BY pb.organization_id, pb.department_id, f.feed_type_id
        """,
        start,
        end,
    )
    shipment_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            feed_type_id,
            COALESCE(SUM(quantity), 0) AS shipped_kg,
            COALESCE(SUM(COALESCE(unit_price, 0) * quantity), 0) AS shipped_amount,
            MAX(currency) AS currency
        FROM feed_product_shipments
        WHERE shipped_on >= $1
          AND shipped_on < $2
        GROUP BY organization_id, department_id, feed_type_id
        """,
        start,
        end,
    )
    quality_rows = await db.fetch(
        """
        SELECT
            qc.organization_id,
            qc.department_id,
            f.feed_type_id,
            qc.status,
            COUNT(*) AS cnt
        FROM feed_production_quality_checks AS qc
        JOIN feed_production_batches AS pb ON pb.id = qc.production_batch_id
        JOIN feed_formulas AS f ON f.id = pb.formula_id
        WHERE qc.checked_on >= $1
          AND qc.checked_on < $2
        GROUP BY qc.organization_id, qc.department_id, f.feed_type_id, qc.status
        """,
        start,
        end,
    )

    def _empty_entry() -> dict[str, object]:
        return {
            "raw_arrivals_kg": Decimal("0.000"),
            "raw_consumptions_kg": Decimal("0.000"),
            "produced_kg": Decimal("0.000"),
            "shipped_kg": Decimal("0.000"),
            "shipped_amount": Decimal("0.00"),
            "purchased_amount": Decimal("0.00"),
            "quality_passed_count": 0,
            "quality_failed_count": 0,
            "quality_pending_count": 0,
            "currency": None,
        }

    merged: dict[tuple[str, str | None, str | None], dict[str, object]] = defaultdict(_empty_entry)

    def _key(row: object) -> tuple[str, str | None, str | None]:
        return (
            str(row["organization_id"]),
            str(row["department_id"]) if row["department_id"] is not None else None,
            str(row["feed_type_id"]) if row["feed_type_id"] is not None else None,
        )

    for row in arrival_rows:
        entry = merged[_key(row)]
        entry["raw_arrivals_kg"] = Decimal(str(row["raw_arrivals_kg"] or 0)).quantize(Decimal("0.001"))
        entry["purchased_amount"] = Decimal(str(row["purchased_amount"] or 0)).quantize(Decimal("0.01"))
        if row["currency"] is not None and entry["currency"] is None:
            entry["currency"] = str(row["currency"])

    for row in consumption_rows:
        entry = merged[_key(row)]
        entry["raw_consumptions_kg"] = Decimal(str(row["raw_consumptions_kg"] or 0)).quantize(Decimal("0.001"))

    for row in production_rows:
        entry = merged[_key(row)]
        entry["produced_kg"] = Decimal(str(row["produced_kg"] or 0)).quantize(Decimal("0.001"))

    for row in shipment_rows:
        entry = merged[_key(row)]
        entry["shipped_kg"] = Decimal(str(row["shipped_kg"] or 0)).quantize(Decimal("0.001"))
        entry["shipped_amount"] = Decimal(str(row["shipped_amount"] or 0)).quantize(Decimal("0.01"))
        if row["currency"] is not None and entry["currency"] is None:
            entry["currency"] = str(row["currency"])

    status_to_field = {
        "passed": "quality_passed_count",
        "failed": "quality_failed_count",
        "pending": "quality_pending_count",
    }
    for row in quality_rows:
        field = status_to_field.get(str(row["status"]))
        if field is None:
            continue
        entry = merged[_key(row)]
        entry[field] = int(row["cnt"] or 0)

    upserted = 0
    for (organization_id, department_id, feed_type_id), metrics in merged.items():
        payload = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "department_id": department_id,
            "feed_type_id": feed_type_id,
            "month_start": start,
            "raw_arrivals_kg": metrics["raw_arrivals_kg"],
            "raw_consumptions_kg": metrics["raw_consumptions_kg"],
            "produced_kg": metrics["produced_kg"],
            "shipped_kg": metrics["shipped_kg"],
            "shipped_amount": metrics["shipped_amount"],
            "purchased_amount": metrics["purchased_amount"],
            "quality_passed_count": metrics["quality_passed_count"],
            "quality_failed_count": metrics["quality_failed_count"],
            "quality_pending_count": metrics["quality_pending_count"],
            "currency": metrics["currency"] or "UZS",
        }
        await repository.upsert(
            payload=payload,
            conflict_columns=["organization_id", "department_id", "feed_type_id", "month_start"],
            update_columns=[
                "raw_arrivals_kg",
                "raw_consumptions_kg",
                "produced_kg",
                "shipped_kg",
                "shipped_amount",
                "purchased_amount",
                "quality_passed_count",
                "quality_failed_count",
                "quality_pending_count",
                "currency",
            ],
        )
        upserted += 1

    return upserted


async def _upsert_slaughter_monthly_analytics(db: Database, *, start: date, end: date) -> int:
    repository = SlaughterMonthlyAnalyticsRepository(db)

    processing_rows = await db.fetch(
        """
        SELECT
            organization_id,
            department_id,
            poultry_type_id,
            COALESCE(SUM(birds_received), 0) AS birds_received,
            COALESCE(SUM(birds_processed), 0) AS birds_processed,
            COALESCE(SUM(first_sort_count), 0) AS first_sort_count,
            COALESCE(SUM(second_sort_count), 0) AS second_sort_count,
            COALESCE(SUM(bad_count), 0) AS bad_count,
            COALESCE(SUM(first_sort_weight_kg), 0) AS first_sort_weight_kg,
            COALESCE(SUM(second_sort_weight_kg), 0) AS second_sort_weight_kg,
            COALESCE(SUM(bad_weight_kg), 0) AS bad_weight_kg,
            COALESCE(SUM(COALESCE(arrival_unit_price, 0) * COALESCE(arrival_total_weight_kg, 0)), 0) AS purchased_amount,
            MAX(arrival_currency) AS arrival_currency
        FROM slaughter_processings
        WHERE processed_on >= $1
          AND processed_on < $2
        GROUP BY organization_id, department_id, poultry_type_id
        """,
        start,
        end,
    )
    shipment_rows = await db.fetch(
        """
        SELECT
            sp.organization_id,
            sp.department_id,
            COALESCE(sp.poultry_type_id, pr.poultry_type_id) AS poultry_type_id,
            COALESCE(SUM(sh.quantity), 0) AS shipped_quantity_kg,
            COALESCE(SUM(COALESCE(sh.unit_price, 0) * sh.quantity), 0) AS shipped_amount,
            MAX(sh.currency) AS currency
        FROM slaughter_semi_product_shipments AS sh
        JOIN slaughter_semi_products AS sp ON sp.id = sh.semi_product_id
        JOIN slaughter_processings AS pr ON pr.id = sp.processing_id
        WHERE sh.shipped_on >= $1
          AND sh.shipped_on < $2
        GROUP BY sp.organization_id, sp.department_id, COALESCE(sp.poultry_type_id, pr.poultry_type_id)
        """,
        start,
        end,
    )

    def _empty_entry() -> dict[str, object]:
        return {
            "birds_received": 0,
            "birds_processed": 0,
            "first_sort_count": 0,
            "second_sort_count": 0,
            "bad_count": 0,
            "first_sort_weight_kg": Decimal("0.000"),
            "second_sort_weight_kg": Decimal("0.000"),
            "bad_weight_kg": Decimal("0.000"),
            "shipped_quantity_kg": Decimal("0.000"),
            "shipped_amount": Decimal("0.00"),
            "purchased_amount": Decimal("0.00"),
            "currency": None,
        }

    merged: dict[tuple[str, str | None, str | None], dict[str, object]] = defaultdict(_empty_entry)

    def _key(row: object) -> tuple[str, str | None, str | None]:
        return (
            str(row["organization_id"]),
            str(row["department_id"]) if row["department_id"] is not None else None,
            str(row["poultry_type_id"]) if row["poultry_type_id"] is not None else None,
        )

    for row in processing_rows:
        entry = merged[_key(row)]
        entry["birds_received"] = int(row["birds_received"] or 0)
        entry["birds_processed"] = int(row["birds_processed"] or 0)
        entry["first_sort_count"] = int(row["first_sort_count"] or 0)
        entry["second_sort_count"] = int(row["second_sort_count"] or 0)
        entry["bad_count"] = int(row["bad_count"] or 0)
        entry["first_sort_weight_kg"] = Decimal(str(row["first_sort_weight_kg"] or 0)).quantize(Decimal("0.001"))
        entry["second_sort_weight_kg"] = Decimal(str(row["second_sort_weight_kg"] or 0)).quantize(Decimal("0.001"))
        entry["bad_weight_kg"] = Decimal(str(row["bad_weight_kg"] or 0)).quantize(Decimal("0.001"))
        entry["purchased_amount"] = Decimal(str(row["purchased_amount"] or 0)).quantize(Decimal("0.01"))
        if row["arrival_currency"] is not None and entry["currency"] is None:
            entry["currency"] = str(row["arrival_currency"])

    for row in shipment_rows:
        entry = merged[_key(row)]
        entry["shipped_quantity_kg"] = Decimal(str(row["shipped_quantity_kg"] or 0)).quantize(Decimal("0.001"))
        entry["shipped_amount"] = Decimal(str(row["shipped_amount"] or 0)).quantize(Decimal("0.01"))
        if row["currency"] is not None and entry["currency"] is None:
            entry["currency"] = str(row["currency"])

    upserted = 0
    for (organization_id, department_id, poultry_type_id), metrics in merged.items():
        payload = {
            "id": str(uuid4()),
            "organization_id": organization_id,
            "department_id": department_id,
            "poultry_type_id": poultry_type_id,
            "month_start": start,
            "birds_received": metrics["birds_received"],
            "birds_processed": metrics["birds_processed"],
            "first_sort_count": metrics["first_sort_count"],
            "second_sort_count": metrics["second_sort_count"],
            "bad_count": metrics["bad_count"],
            "first_sort_weight_kg": metrics["first_sort_weight_kg"],
            "second_sort_weight_kg": metrics["second_sort_weight_kg"],
            "bad_weight_kg": metrics["bad_weight_kg"],
            "shipped_quantity_kg": metrics["shipped_quantity_kg"],
            "shipped_amount": metrics["shipped_amount"],
            "purchased_amount": metrics["purchased_amount"],
            "currency": metrics["currency"] or "UZS",
        }
        await repository.upsert(
            payload=payload,
            conflict_columns=["organization_id", "department_id", "poultry_type_id", "month_start"],
            update_columns=[
                "birds_received",
                "birds_processed",
                "first_sort_count",
                "second_sort_count",
                "bad_count",
                "first_sort_weight_kg",
                "second_sort_weight_kg",
                "bad_weight_kg",
                "shipped_quantity_kg",
                "shipped_amount",
                "purchased_amount",
                "currency",
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
                feed_count = await _upsert_feed_monthly_analytics(db, start=month_start, end=month_end)
                slaughter_count = await _upsert_slaughter_monthly_analytics(db, start=month_start, end=month_end)

            refreshed.append(
                {
                    "month_start": month_start.isoformat(),
                    "egg_rows": egg_count,
                    "incubation_rows": incubation_count,
                    "factory_rows": factory_count,
                    "feed_rows": feed_count,
                    "slaughter_rows": slaughter_count,
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


@broker.task(task_name="send_telegram_admin_alert")
async def send_telegram_admin_alert_task(event_payload: dict[str, object]) -> dict[str, object]:
    settings = get_settings()
    db = Database(
        dsn=settings.database_url,
        min_size=settings.postgres_pool_min_size,
        max_size=settings.postgres_pool_max_size,
        command_timeout=settings.request_timeout_seconds,
    )
    await db.connect()
    try:
        return await deliver_operational_admin_alert(db, event_payload)
    finally:
        await db.disconnect()
