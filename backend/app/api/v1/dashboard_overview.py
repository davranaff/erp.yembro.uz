from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.schemas.stats import (
    DashboardAlertSchema,
    DashboardChartSchema,
    DashboardChartSeriesSchema,
    DashboardExecutiveDashboardSchema,
    DashboardMetricSchema,
    DashboardOverviewResponseSchema,
    DashboardOverviewScopeSchema,
    DashboardSeriesPointSchema,
    DashboardTableItemSchema,
    DashboardTableSchema,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _to_float(value: object | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _to_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_date(value: object | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value

    raw = str(value).strip()
    if not raw:
        return None
    return date.fromisoformat(raw[:10])


def _round_value(value: float) -> float:
    return round(value, 2)


def _department_label(department: dict[str, object] | None) -> str:
    if department is None:
        return ""

    for key in ("name", "code", "id"):
        text = _to_text(department.get(key))
        if text:
            return text

    return ""


def _date_condition(column: str, start_param: int, end_param: int) -> str:
    return (
        f"({column} >= COALESCE(${start_param}, {column})) "
        f"AND ({column} <= COALESCE(${end_param}, {column}))"
    )


def _safe_delta_percent(current_value: float, previous_value: float) -> float:
    if previous_value == 0:
        if current_value == 0:
            return 0.0
        return 100.0 if current_value > 0 else -100.0
    return _round_value(((current_value - previous_value) / abs(previous_value)) * 100)


def _trend_from_delta(delta: float | None) -> str | None:
    if delta is None:
        return None
    if abs(delta) < 0.005:
        return "flat"
    return "up" if delta > 0 else "down"


def _kpi_status(metric_key: str, value: float) -> str:
    if metric_key == "health_index":
        if value >= 75:
            return "good"
        if value >= 55:
            return "warning"
        return "bad"

    if metric_key in {"operating_profit", "net_cashflow"}:
        if value > 0:
            return "good"
        if value == 0:
            return "warning"
        return "bad"

    if metric_key == "value_chain_loss_rate":
        if value <= 5:
            return "good"
        if value <= 12:
            return "warning"
        return "bad"

    if metric_key == "active_risks":
        if value <= 1:
            return "good"
        if value <= 3:
            return "warning"
        return "bad"

    if metric_key == "value_chain_output":
        if value <= 0:
            return "warning"
        return "good"

    return "neutral"


def _metric(
    *,
    key: str,
    label: str,
    value: float,
    unit: str | None,
    previous_value: float | None,
) -> DashboardMetricSchema:
    delta = _round_value(value - previous_value) if previous_value is not None else None
    delta_percent = (
        _safe_delta_percent(value, previous_value)
        if previous_value is not None
        else None
    )
    return DashboardMetricSchema(
        key=key,
        label=label,
        value=_round_value(value),
        unit=unit,
        previous=_round_value(previous_value) if previous_value is not None else None,
        delta=delta,
        deltaPercent=delta_percent,
        trend=_trend_from_delta(delta),
        status=_kpi_status(key, value),
    )


def _series(
    key: str,
    label: str,
    points: list[tuple[str, float]],
) -> DashboardChartSeriesSchema:
    return DashboardChartSeriesSchema(
        key=key,
        label=label,
        points=[
            DashboardSeriesPointSchema(label=point_label, value=_round_value(point_value))
            for point_label, point_value in points
        ],
    )


def _resolve_previous_period(
    start_date: date | None,
    end_date: date | None,
) -> tuple[date | None, date | None]:
    if start_date and end_date:
        window_days = max((end_date - start_date).days + 1, 1)
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=window_days - 1)
        return previous_start, previous_end

    if end_date and not start_date:
        previous_end = end_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
        return previous_start, previous_end

    if start_date and not end_date:
        previous_end = start_date - timedelta(days=1)
        previous_start = previous_end - timedelta(days=29)
        return previous_start, previous_end

    return None, None


def _health_from_scores(module_scores: list[float], operating_profit: float, net_cashflow: float, risk_count: int) -> float:
    average_module_score = sum(module_scores) / len(module_scores) if module_scores else 50.0
    profit_score = 100.0 if operating_profit > 0 else (55.0 if operating_profit == 0 else 30.0)
    cash_score = 100.0 if net_cashflow > 0 else (55.0 if net_cashflow == 0 else 30.0)
    risk_penalty = min(risk_count * 4.0, 25.0)

    raw = (average_module_score * 0.55) + (profit_score * 0.25) + (cash_score * 0.20) - risk_penalty
    return max(0.0, min(100.0, raw))


def _currency_caption(value: float, currency_code: str) -> str:
    formatted = f"{_round_value(value):,.2f}".replace(",", " ")
    return f"{formatted} {currency_code}" if currency_code else formatted


@dataclass
class ModulePulse:
    key: str
    label: str
    revenue: float = 0.0
    output: float = 0.0
    losses: float = 0.0
    loss_rate: float = 0.0
    score: float = 50.0
    status: str = "neutral"


@dataclass
class WindowSnapshot:
    revenue_total: float = 0.0
    expense_total: float = 0.0
    operating_profit: float = 0.0
    net_cashflow: float = 0.0
    output_total: float = 0.0
    losses_total: float = 0.0
    loss_rate: float = 0.0
    finance_series: list[tuple[str, float, float, float, float]] = field(default_factory=list)
    chain_series: list[tuple[str, float, float]] = field(default_factory=list)
    pulse: dict[str, ModulePulse] = field(default_factory=dict)
    expense_categories: list[tuple[str, float]] = field(default_factory=list)
    risk_table_items: list[DashboardTableItemSchema] = field(default_factory=list)

    @property
    def active_risks(self) -> int:
        return len(self.risk_table_items)


async def _resolve_currency_code(db: Database, organization_id: str) -> str:
    row = await db.fetchrow(
        """
        SELECT code
        FROM currencies
        WHERE organization_id = $1
          AND is_active = true
        ORDER BY is_default DESC, sort_order ASC, name ASC, code ASC, id ASC
        LIMIT 1
        """,
        organization_id,
    )
    if row is None or row.get("code") is None:
        return ""
    return str(row["code"]).strip().upper()


async def _fetch_departments(db: Database, organization_id: str) -> list[dict[str, object]]:
    rows = await db.fetch(
        """
        SELECT
            id,
            name,
            code,
            module_key,
            parent_department_id
        FROM departments
        WHERE organization_id = $1
          AND is_active = true
        """,
        organization_id,
    )
    return [
        {
            "id": _to_text(row["id"]),
            "name": row["name"],
            "code": row["code"],
            "module_key": row["module_key"],
            "parent_department_id": _to_text(row["parent_department_id"]) or None,
        }
        for row in rows
    ]


def _build_department_scope(
    departments: list[dict[str, object]],
    department_id: UUID | None,
) -> tuple[set[str] | None, DashboardOverviewScopeSchema]:
    department_map = {
        _to_text(department["id"]): department
        for department in departments
        if _to_text(department["id"])
    }
    children_map: dict[str, list[str]] = defaultdict(list)

    for department in departments:
        department_key = _to_text(department["id"])
        parent_key = _to_text(department.get("parent_department_id")) or None
        if department_key and parent_key:
            children_map[parent_key].append(department_key)

    if department_id is None:
        return None, DashboardOverviewScopeSchema(
            departmentId=None,
            departmentLabel="Все отделы",
            departmentModuleKey=None,
            departmentPath=[],
            startDate=None,
            endDate=None,
        )

    selected_id = str(department_id)
    selected_department = department_map.get(selected_id)
    if selected_department is None:
        raise HTTPException(status_code=404, detail="Department not found")

    scoped_ids: set[str] = set()
    queue = [selected_id]
    while queue:
        current_id = queue.pop()
        if current_id in scoped_ids:
            continue
        scoped_ids.add(current_id)
        queue.extend(children_map.get(current_id, []))

    department_path: list[str] = []
    cursor = selected_id
    visited: set[str] = set()
    while cursor and cursor not in visited:
        visited.add(cursor)
        current_department = department_map.get(cursor)
        if current_department is None:
            break
        department_path.append(_department_label(current_department))
        cursor = _to_text(current_department.get("parent_department_id")) or ""
    department_path.reverse()

    return scoped_ids, DashboardOverviewScopeSchema(
        departmentId=selected_id,
        departmentLabel=_department_label(selected_department),
        departmentModuleKey=_to_text(selected_department.get("module_key")) or None,
        departmentPath=department_path,
        startDate=None,
        endDate=None,
    )


def _to_uuid_list(scoped_department_ids: set[str] | None) -> list[UUID] | None:
    if scoped_department_ids is None:
        return None

    result: list[UUID] = []
    for department_id in scoped_department_ids:
        try:
            result.append(UUID(department_id))
        except ValueError:
            continue

    return result


async def _fetch_revenue_rows(
    db: Database,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
):
    return await db.fetch(
        f"""
        SELECT
            module_key,
            event_date,
            department_id,
            SUM(amount) AS amount
        FROM (
            SELECT
                'egg' AS module_key,
                shipped_on AS event_date,
                department_id,
                (COALESCE(eggs_count, 0) * COALESCE(unit_price, 0)) AS amount
            FROM egg_shipments
            WHERE organization_id = $1

            UNION ALL

            SELECT
                'incubation' AS module_key,
                shipped_on AS event_date,
                department_id,
                (COALESCE(chicks_count, 0) * COALESCE(unit_price, 0)) AS amount
            FROM chick_shipments
            WHERE organization_id = $2

            UNION ALL

            SELECT
                'feed' AS module_key,
                shipped_on AS event_date,
                department_id,
                (COALESCE(quantity, 0) * COALESCE(unit_price, 0)) AS amount
            FROM feed_product_shipments
            WHERE organization_id = $3

            UNION ALL

            SELECT
                'slaughter' AS module_key,
                shipped_on AS event_date,
                department_id,
                (COALESCE(quantity, 0) * COALESCE(unit_price, 0)) AS amount
            FROM slaughter_semi_product_shipments
            WHERE organization_id = $4
        ) events
        WHERE {_date_condition('event_date', 5, 6)}
        GROUP BY module_key, event_date, department_id
        ORDER BY event_date, module_key, department_id
        """,
        organization_id,
        organization_id,
        organization_id,
        organization_id,
        start_date,
        end_date,
    )


async def _fetch_expense_rows(
    db: Database,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
):
    return await db.fetch(
        f"""
        SELECT
            ct.transaction_date AS event_date,
            ca.department_id,
            COALESCE(ct.amount, 0) AS amount,
            COALESCE(NULLIF(c.name, ''), NULLIF(c.code, ''), 'Категория') AS category_label
        FROM cash_transactions ct
        INNER JOIN cash_accounts ca ON ca.id = ct.cash_account_id
        LEFT JOIN expense_categories c ON c.id = ct.category_id
        WHERE ct.organization_id = $1
          AND ct.transaction_type = 'expense'
          AND {_date_condition('ct.transaction_date', 2, 3)}
        ORDER BY ct.transaction_date
        """,
        organization_id,
        start_date,
        end_date,
    )


async def _fetch_cash_rows(
    db: Database,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
):
    return await db.fetch(
        f"""
        SELECT
            ct.transaction_date AS event_date,
            ca.department_id,
            ct.transaction_type,
            ct.amount AS amount
        FROM cash_transactions ct
        INNER JOIN cash_accounts ca ON ca.id = ct.cash_account_id
        WHERE ct.organization_id = $1
          AND ca.organization_id = $2
          AND {_date_condition('ct.transaction_date', 3, 4)}
        ORDER BY ct.transaction_date
        """,
        organization_id,
        organization_id,
        start_date,
        end_date,
    )


async def _fetch_chain_rows(
    db: Database,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
):
    return await db.fetch(
        f"""
        SELECT
            module_key,
            event_date,
            department_id,
            SUM(output_value) AS output_value,
            SUM(loss_value) AS loss_value
        FROM (
            SELECT
                'egg' AS module_key,
                produced_on AS event_date,
                department_id,
                CASE
                    WHEN (COALESCE(eggs_collected, 0) - COALESCE(eggs_broken, 0) - COALESCE(eggs_rejected, 0)) > 0
                    THEN (COALESCE(eggs_collected, 0) - COALESCE(eggs_broken, 0) - COALESCE(eggs_rejected, 0))
                    ELSE 0
                END AS output_value,
                (COALESCE(eggs_broken, 0) + COALESCE(eggs_rejected, 0)) AS loss_value
            FROM egg_production
            WHERE organization_id = $1

            UNION ALL

            SELECT
                'incubation' AS module_key,
                COALESCE(end_date, start_date) AS event_date,
                department_id,
                COALESCE(chicks_hatched, 0) AS output_value,
                (COALESCE(bad_eggs_count, 0) + COALESCE(chicks_destroyed, 0)) AS loss_value
            FROM incubation_runs
            WHERE organization_id = $2

            UNION ALL

            SELECT
                'factory' AS module_key,
                arrived_on AS event_date,
                department_id,
                COALESCE(chicks_count, 0) AS output_value,
                0 AS loss_value
            FROM chick_arrivals
            WHERE organization_id = $3

            UNION ALL

            SELECT
                'feed' AS module_key,
                COALESCE(finished_on, started_on) AS event_date,
                department_id,
                COALESCE(actual_output, 0) AS output_value,
                0 AS loss_value
            FROM feed_production_batches
            WHERE organization_id = $4

            UNION ALL

            SELECT
                'medicine' AS module_key,
                arrived_on AS event_date,
                department_id,
                COALESCE(quantity, 0) AS output_value,
                0 AS loss_value
            FROM medicine_arrivals
            WHERE organization_id = $5

            UNION ALL

            SELECT
                'slaughter' AS module_key,
                processed_on AS event_date,
                department_id,
                COALESCE(birds_processed, 0) AS output_value,
                (COALESCE(second_sort_count, 0) + COALESCE(bad_count, 0)) AS loss_value
            FROM slaughter_processings
            WHERE organization_id = $6
        ) chain_events
        WHERE {_date_condition('event_date', 7, 8)}
        GROUP BY module_key, event_date, department_id
        ORDER BY event_date, module_key, department_id
        """,
        organization_id,
        organization_id,
        organization_id,
        organization_id,
        organization_id,
        organization_id,
        start_date,
        end_date,
    )


def _build_department_pulse(
    *,
    department_labels: dict[str, str],
    revenue_by_department: dict[str, float],
    output_by_department: dict[str, float],
    losses_by_department: dict[str, float],
) -> dict[str, ModulePulse]:
    department_keys = (
        set(revenue_by_department)
        | set(output_by_department)
        | set(losses_by_department)
    )
    max_revenue = max(revenue_by_department.values(), default=0.0)
    max_output = max(output_by_department.values(), default=0.0)

    result: dict[str, ModulePulse] = {}
    for department_key in department_keys:
        revenue = revenue_by_department.get(department_key, 0.0)
        output = output_by_department.get(department_key, 0.0)
        losses = losses_by_department.get(department_key, 0.0)
        denominator = output + losses
        loss_rate = (losses / denominator * 100.0) if denominator > 0 else 0.0

        if denominator <= 0:
            quality_score = 45.0
        elif loss_rate <= 5:
            quality_score = 100.0
        elif loss_rate <= 12:
            quality_score = 75.0
        elif loss_rate <= 20:
            quality_score = 55.0
        else:
            quality_score = 35.0

        revenue_score = 45.0 + ((revenue / max_revenue) * 55.0) if max_revenue > 0 else 45.0
        output_score = 45.0 + ((output / max_output) * 55.0) if max_output > 0 else 45.0
        score = (quality_score * 0.45) + (revenue_score * 0.30) + (output_score * 0.25)

        if score >= 75:
            status = "good"
        elif score >= 55:
            status = "warning"
        else:
            status = "bad"

        result[department_key] = ModulePulse(
            key=department_key,
            label=department_labels.get(department_key) or department_key,
            revenue=revenue,
            output=output,
            losses=losses,
            loss_rate=loss_rate,
            score=_round_value(score),
            status=status,
        )

    return result


def _build_risk_table_items(
    *,
    currency_code: str,
    operating_profit: float,
    net_cashflow: float,
    pulse: dict[str, ModulePulse],
    expense_by_category: dict[str, float],
) -> list[DashboardTableItemSchema]:
    items: list[DashboardTableItemSchema] = []

    if operating_profit < 0:
        items.append(
            DashboardTableItemSchema(
                key="risk:operating_loss",
                label="Операционный убыток",
                value=_round_value(abs(operating_profit)),
                unit=currency_code,
                caption="За период расходы превысили выручку.",
            )
        )

    if net_cashflow < 0:
        items.append(
            DashboardTableItemSchema(
                key="risk:negative_cashflow",
                label="Отрицательный денежный поток",
                value=_round_value(abs(net_cashflow)),
                unit=currency_code,
                caption="Денежный отток выше притока.",
            )
        )

    high_loss_modules = [module for module in pulse.values() if module.loss_rate > 12]
    high_loss_modules.sort(key=lambda module: module.loss_rate, reverse=True)
    for module in high_loss_modules[:4]:
        items.append(
            DashboardTableItemSchema(
                key=f"risk:loss:{module.key}",
                label=f"{module.label}: высокий уровень потерь",
                value=_round_value(module.loss_rate),
                unit="%",
                caption=f"Потери {module.losses:.0f} при выпуске {module.output:.0f}",
            )
        )

    top_expense_categories = sorted(
        expense_by_category.items(),
        key=lambda entry: entry[1],
        reverse=True,
    )[:3]
    for category_name, amount in top_expense_categories:
        items.append(
            DashboardTableItemSchema(
                key=f"risk:expense:{category_name}",
                label=f"Расходная категория: {category_name}",
                value=_round_value(amount),
                unit=currency_code,
                caption="Крупная доля расходов за выбранный период.",
            )
        )

    return items[:8]


async def _collect_window_snapshot(
    *,
    db: Database,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
    departments: list[dict[str, object]],
    currency_code: str,
) -> WindowSnapshot:
    revenue_rows = await _fetch_revenue_rows(
        db,
        organization_id,
        start_date,
        end_date,
    )
    expense_rows = await _fetch_expense_rows(
        db,
        organization_id,
        start_date,
        end_date,
    )
    cash_rows = await _fetch_cash_rows(
        db,
        organization_id,
        start_date,
        end_date,
    )
    chain_rows = await _fetch_chain_rows(
        db,
        organization_id,
        start_date,
        end_date,
    )
    scoped_department_ids = (
        {str(department_id) for department_id in department_ids}
        if department_ids is not None
        else None
    )

    revenue_total = 0.0
    expense_total = 0.0
    net_cashflow = 0.0
    output_total = 0.0
    losses_total = 0.0

    revenue_by_date: dict[date, float] = defaultdict(float)
    expense_by_date: dict[date, float] = defaultdict(float)
    cash_by_date: dict[date, float] = defaultdict(float)
    output_by_date: dict[date, float] = defaultdict(float)
    losses_by_date: dict[date, float] = defaultdict(float)

    revenue_by_department: dict[str, float] = defaultdict(float)
    output_by_department: dict[str, float] = defaultdict(float)
    losses_by_department: dict[str, float] = defaultdict(float)

    expense_by_category: dict[str, float] = defaultdict(float)
    department_labels = {
        _to_text(department.get("id")): _department_label(department)
        for department in departments
        if _to_text(department.get("id"))
    }

    for row in revenue_rows:
        event_date = _parse_date(row.get("event_date"))
        if event_date is None:
            continue
        department_id = _to_text(row.get("department_id"))
        if scoped_department_ids is not None and department_id not in scoped_department_ids:
            continue

        amount = _to_float(row.get("amount"))

        revenue_total += amount
        revenue_by_date[event_date] += amount
        if department_id:
            revenue_by_department[department_id] += amount

    for row in expense_rows:
        event_date = _parse_date(row.get("event_date"))
        if event_date is None:
            continue
        department_id = _to_text(row.get("department_id"))
        if scoped_department_ids is not None and department_id not in scoped_department_ids:
            continue

        amount = _to_float(row.get("amount"))
        category_label = _to_text(row.get("category_label")) or "Категория"

        expense_total += amount
        expense_by_date[event_date] += amount
        expense_by_category[category_label] += amount

    for row in cash_rows:
        event_date = _parse_date(row.get("event_date"))
        if event_date is None:
            continue
        department_id = _to_text(row.get("department_id"))
        if scoped_department_ids is not None and department_id not in scoped_department_ids:
            continue

        amount = _to_float(row.get("amount"))
        transaction_type = _to_text(row.get("transaction_type")).lower()
        is_positive = transaction_type in {"income", "transfer_in", "adjustment"}
        signed_amount = amount if is_positive else -amount

        net_cashflow += signed_amount
        cash_by_date[event_date] += signed_amount

    for row in chain_rows:
        event_date = _parse_date(row.get("event_date"))
        if event_date is None:
            continue
        department_id = _to_text(row.get("department_id"))
        if scoped_department_ids is not None and department_id not in scoped_department_ids:
            continue

        output_value = _to_float(row.get("output_value"))
        loss_value = _to_float(row.get("loss_value"))

        output_total += output_value
        losses_total += loss_value
        output_by_date[event_date] += output_value
        losses_by_date[event_date] += loss_value
        if department_id:
            output_by_department[department_id] += output_value
            losses_by_department[department_id] += loss_value

    pulse = _build_department_pulse(
        department_labels=department_labels,
        revenue_by_department=revenue_by_department,
        output_by_department=output_by_department,
        losses_by_department=losses_by_department,
    )

    risk_table_items = _build_risk_table_items(
        currency_code=currency_code,
        operating_profit=revenue_total - expense_total,
        net_cashflow=net_cashflow,
        pulse=pulse,
        expense_by_category=expense_by_category,
    )

    finance_dates = sorted(set(revenue_by_date) | set(expense_by_date) | set(cash_by_date))
    finance_series = [
        (
            bucket.isoformat(),
            revenue_by_date.get(bucket, 0.0),
            expense_by_date.get(bucket, 0.0),
            revenue_by_date.get(bucket, 0.0) - expense_by_date.get(bucket, 0.0),
            cash_by_date.get(bucket, 0.0),
        )
        for bucket in finance_dates
    ]

    chain_dates = sorted(set(output_by_date) | set(losses_by_date))
    chain_series = [
        (
            bucket.isoformat(),
            output_by_date.get(bucket, 0.0),
            losses_by_date.get(bucket, 0.0),
        )
        for bucket in chain_dates
    ]

    denominator = output_total + losses_total
    loss_rate = (losses_total / denominator * 100.0) if denominator > 0 else 0.0
    top_expense_categories = sorted(
        expense_by_category.items(),
        key=lambda entry: entry[1],
        reverse=True,
    )[:6]

    return WindowSnapshot(
        revenue_total=_round_value(revenue_total),
        expense_total=_round_value(expense_total),
        operating_profit=_round_value(revenue_total - expense_total),
        net_cashflow=_round_value(net_cashflow),
        output_total=_round_value(output_total),
        losses_total=_round_value(losses_total),
        loss_rate=_round_value(loss_rate),
        finance_series=finance_series,
        chain_series=chain_series,
        pulse=pulse,
        expense_categories=[(label, _round_value(amount)) for label, amount in top_expense_categories],
        risk_table_items=risk_table_items,
    )


def _build_executive_dashboard(
    *,
    current_snapshot: WindowSnapshot,
    previous_snapshot: WindowSnapshot | None,
    currency_code: str,
) -> DashboardExecutiveDashboardSchema:
    previous_health = None
    previous_operating_profit = previous_snapshot.operating_profit if previous_snapshot else None
    previous_net_cashflow = previous_snapshot.net_cashflow if previous_snapshot else None
    previous_output_total = previous_snapshot.output_total if previous_snapshot else None
    previous_loss_rate = previous_snapshot.loss_rate if previous_snapshot else None
    previous_active_risks = float(previous_snapshot.active_risks) if previous_snapshot else None

    module_scores = [pulse.score for pulse in current_snapshot.pulse.values()]
    health_index = _health_from_scores(
        module_scores,
        current_snapshot.operating_profit,
        current_snapshot.net_cashflow,
        current_snapshot.active_risks,
    )

    if previous_snapshot is not None:
        previous_health = _health_from_scores(
            [pulse.score for pulse in previous_snapshot.pulse.values()],
            previous_snapshot.operating_profit,
            previous_snapshot.net_cashflow,
            previous_snapshot.active_risks,
        )

    pulse_items = sorted(
        current_snapshot.pulse.values(),
        key=lambda pulse: pulse.score,
        reverse=True,
    )
    revenue_pulse_items = sorted(
        pulse_items,
        key=lambda pulse: pulse.revenue,
        reverse=True,
    )
    operations_pulse_items = sorted(
        pulse_items,
        key=lambda pulse: pulse.output,
        reverse=True,
    )
    loss_pulse_items = sorted(
        pulse_items,
        key=lambda pulse: pulse.loss_rate,
        reverse=True,
    )

    department_table = DashboardTableSchema(
        key="departments_performance",
        title="Общая картина по отделам",
        description="Сводка по отделам: score, потери, выручка и выпуск.",
        items=[
            DashboardTableItemSchema(
                key=pulse.key,
                label=pulse.label,
                value=pulse.score,
                unit="%",
                caption=(
                    f"Статус {pulse.status.upper()} · Потери {pulse.loss_rate:.2f}% · "
                    f"Выручка {_currency_caption(pulse.revenue, currency_code)} · "
                    f"Выпуск {pulse.output:.0f} ед."
                ),
            )
            for pulse in pulse_items
        ][:8],
    )

    risk_table = DashboardTableSchema(
        key="top_risk_summary",
        title="Top risk summary",
        description="Риски, которые требуют внимания директора в первую очередь.",
        items=current_snapshot.risk_table_items,
    )

    alerts: list[DashboardAlertSchema] = []
    if health_index < 55:
        alerts.append(
            DashboardAlertSchema(
                key="health_index_bad",
                level="critical",
                title="Индекс здоровья бизнеса просел",
                message="Общий индекс ниже безопасного уровня.",
                value=_round_value(health_index),
                unit="%",
            )
        )

    if current_snapshot.operating_profit < 0:
        alerts.append(
            DashboardAlertSchema(
                key="operating_loss",
                level="critical",
                title="Операционный убыток",
                message="Расходы превышают выручку за выбранный период.",
                value=_round_value(current_snapshot.operating_profit),
                unit=currency_code,
            )
        )

    if current_snapshot.net_cashflow < 0:
        alerts.append(
            DashboardAlertSchema(
                key="negative_cashflow",
                level="warning",
                title="Отрицательный денежный поток",
                message="Отток денег больше притока за выбранный период.",
                value=_round_value(current_snapshot.net_cashflow),
                unit=currency_code,
            )
        )

    bad_modules = [pulse for pulse in current_snapshot.pulse.values() if pulse.status == "bad"]
    if bad_modules:
        alerts.append(
            DashboardAlertSchema(
                key="modules_in_bad_zone",
                level="warning",
                title="Есть департаменты в красной зоне",
                message="Минимум один департамент показывает слабый операционный score.",
                value=float(len(bad_modules)),
                unit="шт",
            )
        )

    return DashboardExecutiveDashboardSchema(
        kpis=[
            _metric(
                key="health_index",
                label="Индекс здоровья бизнеса",
                value=health_index,
                unit="%",
                previous_value=previous_health,
            ),
            _metric(
                key="operating_profit",
                label="Операционная прибыль",
                value=current_snapshot.operating_profit,
                unit=currency_code,
                previous_value=previous_operating_profit,
            ),
            _metric(
                key="net_cashflow",
                label="Денежный поток",
                value=current_snapshot.net_cashflow,
                unit=currency_code,
                previous_value=previous_net_cashflow,
            ),
            _metric(
                key="value_chain_output",
                label="Сквозной выпуск",
                value=current_snapshot.output_total,
                unit="ед.",
                previous_value=previous_output_total,
            ),
            _metric(
                key="value_chain_loss_rate",
                label="Сквозные потери",
                value=current_snapshot.loss_rate,
                unit="%",
                previous_value=previous_loss_rate,
            ),
            _metric(
                key="active_risks",
                label="Активные риски",
                value=float(current_snapshot.active_risks),
                unit="шт",
                previous_value=previous_active_risks,
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="finance_overview",
                title="Финансы: выручка, расходы, прибыль, cashflow",
                description="Ежедневная динамика ключевых финансовых сигналов.",
                type="line",
                unit=currency_code,
                series=[
                    _series(
                        "revenue",
                        "Выручка",
                        [(label, revenue) for label, revenue, _, _, _ in current_snapshot.finance_series],
                    ),
                    _series(
                        "expenses",
                        "Расходы",
                        [(label, expenses) for label, _, expenses, _, _ in current_snapshot.finance_series],
                    ),
                    _series(
                        "profit",
                        "Прибыль",
                        [(label, profit) for label, _, _, profit, _ in current_snapshot.finance_series],
                    ),
                    _series(
                        "cashflow",
                        "Cashflow",
                        [(label, cashflow) for label, _, _, _, cashflow in current_snapshot.finance_series],
                    ),
                ],
            ),
            DashboardChartSchema(
                key="value_chain_trend",
                title="Сквозная цепочка: выпуск vs потери",
                description="Как меняется выпуск и уровень потерь в операционной цепочке.",
                type="line",
                unit="ед.",
                series=[
                    _series(
                        "output",
                        "Выпуск",
                        [(label, output) for label, output, _ in current_snapshot.chain_series],
                    ),
                    _series(
                        "losses",
                        "Потери",
                        [(label, losses) for label, _, losses in current_snapshot.chain_series],
                    ),
                ],
            ),
            DashboardChartSchema(
                key="department_contribution",
                title="Общая оценка отделов",
                description="Какие отделы сейчас тянут результат вверх, а какие проседают.",
                type="bar",
                unit="%",
                series=[
                    _series(
                        "score",
                        "Оценка",
                        [(pulse.label, pulse.score) for pulse in pulse_items],
                    )
                ],
            ),
            DashboardChartSchema(
                key="department_revenue",
                title="Выручка по отделам",
                description="Показывает, какие отделы приносят основную выручку за период.",
                type="bar",
                unit=currency_code,
                series=[
                    _series(
                        "revenue",
                        "Выручка",
                        [(pulse.label, pulse.revenue) for pulse in revenue_pulse_items],
                    )
                ],
            ),
            DashboardChartSchema(
                key="department_operations",
                title="Выпуск и потери по отделам",
                description="Сравнение полезного выпуска и объёма потерь по каждому отделу.",
                type="bar",
                unit="ед.",
                series=[
                    _series(
                        "output",
                        "Выпуск",
                        [(pulse.label, pulse.output) for pulse in operations_pulse_items],
                    ),
                    _series(
                        "losses",
                        "Потери",
                        [(pulse.label, pulse.losses) for pulse in operations_pulse_items],
                    ),
                ],
            ),
            DashboardChartSchema(
                key="department_loss_rate",
                title="Доля потерь по отделам",
                description="Показывает, где потери уже выходят за безопасный уровень.",
                type="bar",
                unit="%",
                series=[
                    _series(
                        "loss_rate",
                        "Потери",
                        [(pulse.label, pulse.loss_rate) for pulse in loss_pulse_items],
                    )
                ],
            ),
            DashboardChartSchema(
                key="expense_category_burn",
                title="Куда уходят деньги",
                description="Топ категорий расходов за выбранный период.",
                type="bar",
                unit=currency_code,
                series=[
                    _series(
                        "amount",
                        "Расходы",
                        current_snapshot.expense_categories,
                    )
                ],
            ),
        ],
        tables=[department_table, risk_table],
        alerts=alerts,
    )


@router.get(
    "/overview",
    response_model=DashboardOverviewResponseSchema,
    dependencies=[Depends(get_current_actor), Depends(require_access("dashboard.read"))],
    name="dashboard_overview",
    operation_id="get_dashboard_overview",
)
async def get_dashboard_overview(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    department_id: UUID | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> DashboardOverviewResponseSchema:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")

    departments = await _fetch_departments(db, current_actor.organization_id)
    scoped_department_ids, scope = _build_department_scope(departments, department_id)
    scope = scope.model_copy(update={"startDate": start_date, "endDate": end_date})

    department_uuid_list = _to_uuid_list(scoped_department_ids)
    currency_code = await _resolve_currency_code(db, current_actor.organization_id)

    current_snapshot = await _collect_window_snapshot(
        db=db,
        organization_id=current_actor.organization_id,
        start_date=start_date,
        end_date=end_date,
        department_ids=department_uuid_list,
        departments=departments,
        currency_code=currency_code,
    )

    previous_start_date, previous_end_date = _resolve_previous_period(start_date, end_date)
    previous_snapshot = None
    if previous_start_date is not None and previous_end_date is not None:
        previous_snapshot = await _collect_window_snapshot(
            db=db,
            organization_id=current_actor.organization_id,
            start_date=previous_start_date,
            end_date=previous_end_date,
            department_ids=department_uuid_list,
            departments=departments,
            currency_code=currency_code,
        )

    executive_dashboard = _build_executive_dashboard(
        current_snapshot=current_snapshot,
        previous_snapshot=previous_snapshot,
        currency_code=currency_code,
    )

    return DashboardOverviewResponseSchema(
        generatedAt=datetime.now(timezone.utc),
        currency=currency_code,
        scope=scope,
        executive_dashboard=executive_dashboard,
        department_dashboard=None,
    )


__all__ = ["router"]
