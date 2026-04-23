from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.feed_shrinkage import (
    FeedShrinkageRunner,
    compute_compound_shrinkage,
)


ORGANIZATION_ID = "11111111-1111-1111-1111-111111111111"
DEPARTMENT_ID = "77771111-1111-1111-1111-111111111111"
WAREHOUSE_ID = "5fe5f27e-e501-536f-ab8b-c98ed5a8234e"
# First corn arrival from fixtures, arrived 30 days ago, 18 000 kg.
RAW_ARRIVAL_ID = "76111111-1111-1111-1111-111111111101"
INGREDIENT_ID = "73111111-1111-1111-1111-111111111101"


# ---------- pure algorithm ----------


def test_compound_shrinkage_matches_spec_appendix_a() -> None:
    """Appendix A walks through 7 compound periods at 0.8% / 7 days.

    Initial 1000 kg, max_total=5%. The last period clips to stay at the
    5% cap and freezes the state.
    """
    result = compute_compound_shrinkage(
        current_balance=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        percent_per_period=Decimal("0.8"),
        max_total_percent=Decimal("5"),
        full_periods=7,
    )
    assert result.periods_applied == 7
    assert result.freeze_after is True
    # Cap is exactly 5% of 1000 = 50 kg.
    assert result.total_loss == Decimal("50.000")


def test_compound_shrinkage_without_cap_is_pure_compound() -> None:
    result = compute_compound_shrinkage(
        current_balance=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        percent_per_period=Decimal("0.8"),
        max_total_percent=None,
        full_periods=3,
    )
    # 1000 → 992 → 984.064 → 976.191 (each delta rounded to 3 dp
    # before subtraction, so the sum is 8.000 + 7.936 + 7.873).
    assert result.periods_applied == 3
    assert result.freeze_after is False
    assert result.total_loss == Decimal("23.809")


def test_compound_shrinkage_respects_already_accumulated_loss() -> None:
    """If we already lost 45 kg of the 50 kg cap, only 5 kg more are allowed."""
    result = compute_compound_shrinkage(
        current_balance=Decimal("955"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("45"),
        percent_per_period=Decimal("0.8"),
        max_total_percent=Decimal("5"),
        full_periods=3,
    )
    assert result.freeze_after is True
    assert result.total_loss == Decimal("5.000")


def test_compound_shrinkage_zero_periods_returns_nothing() -> None:
    result = compute_compound_shrinkage(
        current_balance=Decimal("1000"),
        initial_quantity=Decimal("1000"),
        accumulated_loss=Decimal("0"),
        percent_per_period=Decimal("0.8"),
        max_total_percent=None,
        full_periods=0,
    )
    assert result.periods_applied == 0
    assert result.total_loss == Decimal("0")


def test_compound_shrinkage_never_loses_more_than_remaining() -> None:
    """Compound shrinkage is asymptotic — it can never take more from
    the lot than is physically present. Total loss stays under the
    initial balance even with an absurdly high percent."""
    result = compute_compound_shrinkage(
        current_balance=Decimal("3"),
        initial_quantity=Decimal("100"),
        accumulated_loss=Decimal("0"),
        percent_per_period=Decimal("50"),
        max_total_percent=None,
        full_periods=5,
    )
    assert result.total_loss > Decimal("0")
    assert result.total_loss < Decimal("3")


# ---------- runner: integration with db ----------


async def _make_profile(
    db,
    *,
    ingredient_id: str = INGREDIENT_ID,
    warehouse_id: str | None = None,
    period_days: int = 7,
    percent_per_period: str = "0.8",
    max_total_percent: str | None = "5",
    stop_after_days: int | None = None,
    starts_after_days: int = 0,
) -> str:
    profile_id = str(uuid4())
    await db.execute(
        """
        INSERT INTO feed_shrinkage_profiles
        (id, organization_id, target_type, ingredient_id, feed_type_id,
         warehouse_id, period_days, percent_per_period, max_total_percent,
         stop_after_days, starts_after_days, is_active, note)
        VALUES ($1, $2, 'ingredient', $3, NULL, $4, $5, $6, $7, $8, $9, true, NULL)
        """,
        profile_id,
        ORGANIZATION_ID,
        ingredient_id,
        warehouse_id,
        period_days,
        Decimal(percent_per_period),
        Decimal(max_total_percent) if max_total_percent is not None else None,
        stop_after_days,
        starts_after_days,
    )
    return profile_id


async def _set_arrival_quantity(db, *, arrival_id: str, arrived_on: date, quantity: Decimal) -> None:
    await db.execute(
        "UPDATE feed_raw_arrivals SET arrived_on = $1, quantity = $2 WHERE id = $3",
        arrived_on,
        quantity,
        arrival_id,
    )


@pytest.mark.asyncio
async def test_runner_skips_lot_when_no_profile(sqlite_db) -> None:
    runner = FeedShrinkageRunner(sqlite_db)
    outcomes = await runner.apply_for_organization(ORGANIZATION_ID, on_date=date.today())
    # With no shrinkage profiles configured, the runner is a no-op — it
    # must not write state or movements.
    assert outcomes == []
    row = await sqlite_db.fetchrow(
        "SELECT COUNT(*) AS n FROM feed_lot_shrinkage_state"
    )
    assert int(row["n"]) == 0


@pytest.mark.asyncio
async def test_runner_applies_one_cycle_to_raw_arrival(sqlite_db) -> None:
    # Anchor arrival at exactly 7 days ago with 1000 kg to match the
    # simplest Appendix A math: one period of 0.8% yields 8 kg loss.
    today = date.today()
    await _set_arrival_quantity(
        sqlite_db,
        arrival_id=RAW_ARRIVAL_ID,
        arrived_on=today - timedelta(days=7),
        quantity=Decimal("1000"),
    )
    await _make_profile(sqlite_db, max_total_percent=None)

    runner = FeedShrinkageRunner(sqlite_db)
    outcomes = await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)

    assert len(outcomes) == 1
    outcome = outcomes[0]
    assert outcome.lot_type == "raw_arrival"
    assert outcome.lot_id == RAW_ARRIVAL_ID
    assert outcome.periods_applied == 1
    assert outcome.loss_quantity == Decimal("8.000")
    assert outcome.is_frozen is False


@pytest.mark.asyncio
async def test_runner_is_idempotent_on_same_day(sqlite_db) -> None:
    today = date.today()
    await _set_arrival_quantity(
        sqlite_db,
        arrival_id=RAW_ARRIVAL_ID,
        arrived_on=today - timedelta(days=7),
        quantity=Decimal("1000"),
    )
    await _make_profile(sqlite_db, max_total_percent=None)
    runner = FeedShrinkageRunner(sqlite_db)

    first_run = await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)
    assert len(first_run) == 1

    second_run = await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)
    # Re-running on the same date must not double-apply — last_applied_on
    # is already today, so no full period has elapsed.
    assert second_run == []


@pytest.mark.asyncio
async def test_runner_freezes_when_stop_after_days_is_exceeded(sqlite_db) -> None:
    today = date.today()
    await _set_arrival_quantity(
        sqlite_db,
        arrival_id=RAW_ARRIVAL_ID,
        arrived_on=today - timedelta(days=120),
        quantity=Decimal("1000"),
    )
    await _make_profile(
        sqlite_db,
        stop_after_days=90,
        max_total_percent=None,
    )

    runner = FeedShrinkageRunner(sqlite_db)
    outcomes = await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)
    # Past the stop cutoff — no loss is recorded, but a frozen state row
    # is created so subsequent runs skip the lot instantly.
    assert outcomes == []
    row = await sqlite_db.fetchrow(
        "SELECT is_frozen FROM feed_lot_shrinkage_state WHERE lot_id = $1",
        RAW_ARRIVAL_ID,
    )
    assert row is not None
    assert bool(row["is_frozen"]) is True


@pytest.mark.asyncio
async def test_runner_prefers_warehouse_scoped_profile(sqlite_db) -> None:
    today = date.today()
    await _set_arrival_quantity(
        sqlite_db,
        arrival_id=RAW_ARRIVAL_ID,
        arrived_on=today - timedelta(days=7),
        quantity=Decimal("1000"),
    )
    # Global (warehouse_id NULL) profile says 0.5%. Warehouse-scoped
    # profile on the same warehouse says 2.0%. The warehouse-scoped one
    # must win.
    await _make_profile(
        sqlite_db,
        warehouse_id=None,
        percent_per_period="0.5",
        max_total_percent=None,
    )
    await _make_profile(
        sqlite_db,
        warehouse_id=WAREHOUSE_ID,
        percent_per_period="2.0",
        max_total_percent=None,
    )

    runner = FeedShrinkageRunner(sqlite_db)
    outcomes = await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)
    assert len(outcomes) == 1
    assert outcomes[0].loss_quantity == Decimal("20.000")


@pytest.mark.asyncio
async def test_reset_lot_zeroes_state_and_replays(sqlite_db) -> None:
    today = date.today()
    await _set_arrival_quantity(
        sqlite_db,
        arrival_id=RAW_ARRIVAL_ID,
        arrived_on=today - timedelta(days=14),
        quantity=Decimal("1000"),
    )
    await _make_profile(sqlite_db, max_total_percent=None)
    runner = FeedShrinkageRunner(sqlite_db)

    await runner.apply_for_organization(ORGANIZATION_ID, on_date=today - timedelta(days=7))
    await runner.apply_for_organization(ORGANIZATION_ID, on_date=today)
    state_row = await sqlite_db.fetchrow(
        "SELECT id, accumulated_loss FROM feed_lot_shrinkage_state "
        "WHERE lot_id = $1",
        RAW_ARRIVAL_ID,
    )
    assert state_row is not None
    state_id = str(state_row["id"])
    assert Decimal(str(state_row["accumulated_loss"])) > Decimal("0")

    movement_rows_before = await sqlite_db.fetch(
        "SELECT id FROM stock_movements "
        "WHERE reference_table = 'feed_lot_shrinkage_state' AND reference_id = $1",
        state_id,
    )
    assert len(movement_rows_before) >= 1

    outcome = await runner.reset_lot(state_id)
    # Reset replays the algorithm from scratch on today, so we end up
    # with a single compound cycle covering the whole window.
    assert outcome is not None

    state_after = await sqlite_db.fetchrow(
        "SELECT accumulated_loss, last_applied_on FROM feed_lot_shrinkage_state "
        "WHERE id = $1",
        state_id,
    )
    assert Decimal(str(state_after["accumulated_loss"])) == outcome.accumulated_loss
