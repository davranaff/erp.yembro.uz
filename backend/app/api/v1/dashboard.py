from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import CurrentActor, db_dependency, get_current_actor, require_access
from app.db.pool import Database
from app.schemas.stats import (
    DashboardAlertSchema,
    DashboardAnalyticsResponseSchema,
    DashboardDepartmentDashboardSchema,
    DashboardBreakdownItemSchema,
    DashboardBreakdownSchema,
    DashboardChartSchema,
    DashboardChartSeriesSchema,
    DashboardMetricSchema,
    DashboardModuleSchema,
    DashboardOverviewScopeSchema,
    DashboardSectionSchema,
    DashboardSeriesPointSchema,
    DashboardTableItemSchema,
    DashboardTableSchema,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _date_condition(column: str) -> str:
    return f"($1::date IS NULL OR {column} >= $1::date) AND ($2::date IS NULL OR {column} <= $2::date)"


def _department_condition(column: str) -> str:
    return f"($3::uuid[] IS NULL OR {column} = ANY($3::uuid[]))"


def _to_float(value: object | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


def _to_label(value: object | None) -> str:
    if value is None:
        return "—"
    return str(value)


def _ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def _average_unit_price(total_amount: float, total_quantity: float) -> float:
    if total_quantity <= 0:
        return 0.0
    return round(total_amount / total_quantity, 2)


POSITIVE_PERCENT_METRIC_KEYS = {
    "grade_1_share",
    "hatch_rate",
    "shipment_rate",
    "turnover_rate",
    "process_rate",
    "first_sort_share",
}
NEGATIVE_PERCENT_METRIC_KEYS = {"loss_rate"}
NEGATIVE_ABSOLUTE_METRIC_KEYS = {
    "critical_stock_items",
    "expiring_batches",
    "expired_batches",
    "bad_eggs",
    "bad_eggs_total",
}
FINANCIAL_BALANCE_METRIC_KEYS = {"operating_profit", "financial_result", "net_cashflow"}
LOW_CASH_METRIC_KEYS = {"cash_balance"}


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


def _safe_delta_percent(current_value: float, previous_value: float) -> float:
    if previous_value == 0:
        if current_value == 0:
            return 0.0
        return 100.0 if current_value > 0 else -100.0
    return round(((current_value - previous_value) / abs(previous_value)) * 100, 2)


def _trend_from_delta(delta: float) -> str:
    if abs(delta) < 0.005:
        return "flat"
    return "up" if delta > 0 else "down"


def _metric_status(metric: DashboardMetricSchema) -> str:
    metric_key = metric.key
    value = metric.value

    if metric.unit == "%":
        if metric_key in NEGATIVE_PERCENT_METRIC_KEYS:
            if value <= 5:
                return "good"
            if value <= 12:
                return "warning"
            return "bad"

        if metric_key in POSITIVE_PERCENT_METRIC_KEYS:
            if value >= 85:
                return "good"
            if value >= 60:
                return "warning"
            return "bad"

        return "neutral"

    if metric_key in NEGATIVE_ABSOLUTE_METRIC_KEYS:
        if value <= 0:
            return "good"
        if value <= 3:
            return "warning"
        return "bad"

    if metric_key in FINANCIAL_BALANCE_METRIC_KEYS:
        if value > 0:
            return "good"
        if value < 0:
            return "bad"
        return "neutral"

    if metric_key in LOW_CASH_METRIC_KEYS:
        if value > 0:
            return "good"
        if value < 0:
            return "bad"
        return "warning"

    return "neutral"


def _compute_module_health(metrics: list[DashboardMetricSchema]) -> tuple[float, str]:
    statuses = [metric.status for metric in metrics if metric.status and metric.status != "neutral"]
    if not statuses:
        return 50.0, "neutral"

    weights = {"good": 1.0, "warning": 0.55, "bad": 0.15}
    score = (sum(weights.get(status, 0.55) for status in statuses) / len(statuses)) * 100

    if score >= 75:
        return round(score, 2), "good"
    if score >= 50:
        return round(score, 2), "warning"
    return round(score, 2), "bad"


def _enrich_module_metrics(
    current_module: DashboardModuleSchema,
    previous_module: DashboardModuleSchema | None,
) -> DashboardModuleSchema:
    previous_metric_map = {
        metric.key: metric
        for metric in (previous_module.kpis if previous_module is not None else [])
    }

    for metric in current_module.kpis:
        previous_metric = previous_metric_map.get(metric.key)
        if previous_metric is not None:
            previous_value = _to_float(previous_metric.value)
            metric.previous = round(previous_value, 2)
            metric.delta = round(metric.value - previous_value, 2)
            metric.deltaPercent = _safe_delta_percent(metric.value, previous_value)
            metric.trend = _trend_from_delta(metric.delta)
        else:
            metric.previous = None
            metric.delta = None
            metric.deltaPercent = None
            metric.trend = None

        metric.status = _metric_status(metric)

    health_score, health_status = _compute_module_health(current_module.kpis)
    current_module.healthScore = health_score
    current_module.healthStatus = health_status
    return current_module


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


def _replace_currency_token(value: str, currency_code: str) -> str:
    return value.replace(" UZS", f" {currency_code}")


def _apply_currency_code(module: DashboardModuleSchema, currency_code: str) -> DashboardModuleSchema:
    if not currency_code:
        return module

    for kpi in module.kpis:
        if kpi.unit == "UZS":
            kpi.unit = currency_code

    for chart in module.charts:
        if chart.unit == "UZS":
            chart.unit = currency_code
        for series in chart.series:
            for point in series.points:
                point.label = _replace_currency_token(point.label, currency_code)

    for table in module.tables:
        for item in table.items:
            if item.unit == "UZS":
                item.unit = currency_code
            if item.caption:
                item.caption = _replace_currency_token(item.caption, currency_code)

    for alert in module.alerts:
        if alert.unit == "UZS":
            alert.unit = currency_code

    return module


def _metric(*, key: str, label: str, value: float, unit: str | None = None) -> DashboardMetricSchema:
    return DashboardMetricSchema(key=key, label=label, value=max(value, 0.0), unit=unit)


def _signed_metric(*, key: str, label: str, value: float, unit: str | None = None) -> DashboardMetricSchema:
    return DashboardMetricSchema(key=key, label=label, value=round(value, 2), unit=unit)


def _wide_series(
    rows,
    *definitions: tuple[str, str, str],
) -> list[DashboardChartSeriesSchema]:
    result = [
        DashboardChartSeriesSchema(key=key, label=label, points=[])
        for key, label, _ in definitions
    ]

    for row in rows:
        point_label = _to_label(row["label"])
        for index, (_, _, column_name) in enumerate(definitions):
            result[index].points.append(
                DashboardSeriesPointSchema(label=point_label, value=_to_float(row[column_name]))
            )

    return result


def _percentage_series(
    rows,
    *definitions: tuple[str, str, str, str],
) -> list[DashboardChartSeriesSchema]:
    result = [
        DashboardChartSeriesSchema(key=key, label=label, points=[])
        for key, label, _, _ in definitions
    ]

    for row in rows:
        point_label = _to_label(row["label"])
        for index, (_, _, numerator_column, denominator_column) in enumerate(definitions):
            result[index].points.append(
                DashboardSeriesPointSchema(
                    label=point_label,
                    value=_ratio(
                        _to_float(row[numerator_column]),
                        _to_float(row[denominator_column]),
                    ),
                )
            )

    return result


def _category_series(rows) -> list[DashboardChartSeriesSchema]:
    grouped: dict[str, DashboardChartSeriesSchema] = {}

    for row in rows:
        series_key = _to_label(row["series_key"])
        series_label = _to_label(row["series_label"])
        if series_key not in grouped:
            grouped[series_key] = DashboardChartSeriesSchema(key=series_key, label=series_label, points=[])

        grouped[series_key].points.append(
            DashboardSeriesPointSchema(label=_to_label(row["label"]), value=_to_float(row["value"]))
        )

    return list(grouped.values())


def _breakdown_items(rows, *, unit: str | None = None) -> list[DashboardBreakdownItemSchema]:
    items: list[DashboardBreakdownItemSchema] = []

    for row in rows:
        items.append(
            DashboardBreakdownItemSchema(
                key=_to_label(row["key"]),
                label=_to_label(row["label"]),
                value=_to_float(row["value"]),
                unit=_to_label(row["unit"]) if "unit" in row and row["unit"] is not None else unit,
                caption=_to_label(row["caption"]) if "caption" in row and row["caption"] is not None else None,
            )
        )

    return items


def _sum_rows(rows, field: str) -> float:
    return sum(_to_float(row[field]) for row in rows)


@dataclass(slots=True)
class ModuleFinanceAnalytics:
    metrics: list[DashboardMetricSchema]
    charts: list[DashboardChartSchema]
    tables: list[DashboardTableSchema]
    alerts: list[DashboardAlertSchema]


async def _fetch_module_revenue_rows(
    db: Database,
    *,
    module_key: str,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
):
    if module_key == "egg":
        return await db.fetch(
            f"""
            SELECT
                es.shipped_on AS event_date,
                TO_CHAR(es.shipped_on, 'YYYY-MM-DD') AS label,
                SUM(COALESCE(es.unit_price, 0) * es.eggs_count) AS revenue
            FROM egg_shipments es
            INNER JOIN departments d ON d.id = es.department_id
            WHERE {_date_condition('es.shipped_on')}
              AND {_department_condition('es.department_id')}
              AND d.module_key = $4
            GROUP BY es.shipped_on
            ORDER BY es.shipped_on
            """,
            start_date,
            end_date,
            department_ids,
            module_key,
        )

    if module_key == "incubation":
        return await db.fetch(
            f"""
            SELECT
                cs.shipped_on AS event_date,
                TO_CHAR(cs.shipped_on, 'YYYY-MM-DD') AS label,
                SUM(COALESCE(cs.unit_price, 0) * cs.chicks_count) AS revenue
            FROM chick_shipments cs
            INNER JOIN departments d ON d.id = cs.department_id
            WHERE {_date_condition('cs.shipped_on')}
              AND {_department_condition('cs.department_id')}
              AND d.module_key = $4
            GROUP BY cs.shipped_on
            ORDER BY cs.shipped_on
            """,
            start_date,
            end_date,
            department_ids,
            module_key,
        )

    if module_key == "feed":
        return await db.fetch(
            f"""
            SELECT
                fps.shipped_on AS event_date,
                TO_CHAR(fps.shipped_on, 'YYYY-MM-DD') AS label,
                SUM(COALESCE(fps.unit_price, 0) * fps.quantity) AS revenue
            FROM feed_product_shipments fps
            INNER JOIN departments d ON d.id = fps.department_id
            WHERE {_date_condition('fps.shipped_on')}
              AND {_department_condition('fps.department_id')}
              AND d.module_key = $4
            GROUP BY fps.shipped_on
            ORDER BY fps.shipped_on
            """,
            start_date,
            end_date,
            department_ids,
            module_key,
        )

    if module_key == "slaughter":
        return await db.fetch(
            f"""
            SELECT
                ss.shipped_on AS event_date,
                TO_CHAR(ss.shipped_on, 'YYYY-MM-DD') AS label,
                SUM(COALESCE(ss.unit_price, 0) * ss.quantity) AS revenue
            FROM slaughter_semi_product_shipments ss
            INNER JOIN departments d ON d.id = ss.department_id
            WHERE {_date_condition('ss.shipped_on')}
              AND {_department_condition('ss.department_id')}
              AND d.module_key = $4
            GROUP BY ss.shipped_on
            ORDER BY ss.shipped_on
            """,
            start_date,
            end_date,
            department_ids,
            module_key,
        )

    return []


async def _fetch_module_expense_rows(
    db: Database,
    *,
    module_key: str,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
):
    return await db.fetch(
        f"""
        SELECT
            e.id::text AS key,
            e.expense_date AS event_date,
            TO_CHAR(e.expense_date, 'YYYY-MM-DD') AS label,
            COALESCE(NULLIF(e.title, ''), NULLIF(e.item, ''), 'Расход') AS expense_label,
            COALESCE(NULLIF(c.name, ''), NULLIF(c.code, ''), 'Категория') AS category_label,
            COALESCE(e.amount, COALESCE(e.quantity, 0) * COALESCE(e.unit_price, 0), 0) AS amount
        FROM expenses e
        INNER JOIN departments d ON d.id = e.department_id
        LEFT JOIN expense_categories c ON c.id = e.category_id
        WHERE {_date_condition('e.expense_date')}
          AND {_department_condition('e.department_id')}
          AND d.module_key = $4
        ORDER BY e.expense_date DESC, e.created_at DESC
        """,
        start_date,
        end_date,
        department_ids,
        module_key,
    )


async def _fetch_module_cash_rows(
    db: Database,
    *,
    module_key: str,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
):
    return await db.fetch(
        f"""
        SELECT
            ct.transaction_date AS event_date,
            TO_CHAR(ct.transaction_date, 'YYYY-MM-DD') AS label,
            ct.transaction_type,
            ct.amount,
            COALESCE(NULLIF(ct.title, ''), 'Кассовая операция') AS title
        FROM cash_transactions ct
        INNER JOIN cash_accounts ca ON ca.id = ct.cash_account_id
        INNER JOIN departments d ON d.id = ca.department_id
        WHERE {_date_condition('ct.transaction_date')}
          AND {_department_condition('ca.department_id')}
          AND d.module_key = $4
        ORDER BY ct.transaction_date DESC, ct.created_at DESC
        """,
        start_date,
        end_date,
        department_ids,
        module_key,
    )


async def _fetch_module_cash_account_rows(
    db: Database,
    *,
    module_key: str,
    as_of: date | None,
    department_ids: list[UUID] | None,
):
    return await db.fetch(
        """
        WITH balances AS (
            SELECT
                ca.id::text AS key,
                COALESCE(NULLIF(ca.name, ''), NULLIF(ca.code, ''), 'Касса') AS label,
                (
                    COALESCE(ca.opening_balance, 0)
                    + COALESCE(
                        SUM(
                            CASE
                                WHEN ct.transaction_type IN ('income', 'transfer_in', 'adjustment')
                                THEN ct.amount
                                ELSE -ct.amount
                            END
                        ),
                        0
                    )
                ) AS balance,
                COUNT(ct.id) FILTER (WHERE ct.id IS NOT NULL) AS operations_count
            FROM cash_accounts ca
            INNER JOIN departments d ON d.id = ca.department_id
            LEFT JOIN cash_transactions ct
                ON ct.cash_account_id = ca.id
               AND ct.is_active = true
               AND ($1::date IS NULL OR ct.transaction_date <= $1::date)
            WHERE ca.is_active = true
              AND ($2::uuid[] IS NULL OR ca.department_id = ANY($2::uuid[]))
              AND d.module_key = $3
            GROUP BY ca.id, ca.name, ca.code, ca.opening_balance
        )
        SELECT
            key,
            label,
            balance AS value,
            'UZS' AS unit,
            CONCAT('Операций: ', operations_count::text) AS caption
        FROM balances
        WHERE ABS(balance) > 0 OR operations_count > 0
        ORDER BY balance DESC, label
        LIMIT 8
        """,
        as_of,
        department_ids,
        module_key,
    )


async def _build_module_finance_analytics(
    db: Database,
    *,
    module_key: str,
    module_prefix: str,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> ModuleFinanceAnalytics:
    revenue_rows = await _fetch_module_revenue_rows(
        db,
        module_key=module_key,
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )
    expense_rows = await _fetch_module_expense_rows(
        db,
        module_key=module_key,
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )
    cash_rows = await _fetch_module_cash_rows(
        db,
        module_key=module_key,
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )
    cash_account_rows = await _fetch_module_cash_account_rows(
        db,
        module_key=module_key,
        as_of=end_date,
        department_ids=department_ids,
    )

    revenue_by_date: dict[date, float] = defaultdict(float)
    expense_by_date: dict[date, float] = defaultdict(float)
    cashflow_by_date: dict[date, float] = defaultdict(float)
    expense_by_category: dict[str, float] = defaultdict(float)

    for row in revenue_rows:
        event_date = row.get("event_date")
        if not isinstance(event_date, date):
            continue
        revenue_by_date[event_date] += _to_float(row.get("revenue"))

    for row in expense_rows:
        event_date = row.get("event_date")
        if not isinstance(event_date, date):
            continue
        amount = _to_float(row.get("amount"))
        expense_by_date[event_date] += amount
        expense_by_category[_to_label(row.get("category_label"))] += amount

    for row in cash_rows:
        event_date = row.get("event_date")
        if not isinstance(event_date, date):
            continue
        amount = _to_float(row.get("amount"))
        transaction_type = _to_label(row.get("transaction_type")).lower()
        signed_amount = amount if transaction_type in {"income", "transfer_in", "adjustment"} else -amount
        cashflow_by_date[event_date] += signed_amount

    revenue_total = sum(revenue_by_date.values())
    expense_total = sum(expense_by_date.values())
    financial_result = revenue_total - expense_total
    net_cashflow = sum(cashflow_by_date.values())
    cash_balance = _sum_rows(cash_account_rows, "value")

    finance_dates = sorted(set(revenue_by_date) | set(expense_by_date) | set(cashflow_by_date))
    finance_overview_chart = DashboardChartSchema(
        key=f"{module_prefix}_finance_overview",
        title="Деньги отдела",
        description="Выручка, расходы, финрезультат и денежный поток по дням.",
        type="line",
        unit="UZS",
        series=[
            DashboardChartSeriesSchema(
                key="revenue",
                label="Выручка",
                points=[
                    DashboardSeriesPointSchema(label=bucket.isoformat(), value=round(revenue_by_date.get(bucket, 0.0), 2))
                    for bucket in finance_dates
                ],
            ),
            DashboardChartSeriesSchema(
                key="expenses",
                label="Расходы",
                points=[
                    DashboardSeriesPointSchema(label=bucket.isoformat(), value=round(expense_by_date.get(bucket, 0.0), 2))
                    for bucket in finance_dates
                ],
            ),
            DashboardChartSeriesSchema(
                key="result",
                label="Финрезультат",
                points=[
                    DashboardSeriesPointSchema(
                        label=bucket.isoformat(),
                        value=round(revenue_by_date.get(bucket, 0.0) - expense_by_date.get(bucket, 0.0), 2),
                    )
                    for bucket in finance_dates
                ],
            ),
            DashboardChartSeriesSchema(
                key="cashflow",
                label="Денежный поток",
                points=[
                    DashboardSeriesPointSchema(label=bucket.isoformat(), value=round(cashflow_by_date.get(bucket, 0.0), 2))
                    for bucket in finance_dates
                ],
            ),
        ],
    )

    top_expense_categories = sorted(
        expense_by_category.items(),
        key=lambda entry: entry[1],
        reverse=True,
    )[:6]
    expense_categories_chart = DashboardChartSchema(
        key=f"{module_prefix}_expense_categories",
        title="Куда уходят деньги",
        description="Самые тяжёлые категории расходов за выбранный период.",
        type="bar",
        unit="UZS",
        series=[
            DashboardChartSeriesSchema(
                key="amount",
                label="Расходы",
                points=[
                    DashboardSeriesPointSchema(label=label, value=round(amount, 2))
                    for label, amount in top_expense_categories
                ],
            )
        ],
    )

    expense_category_items = [
        DashboardTableItemSchema(
            key=f"{module_prefix}:expense:{index}",
            label=label,
            value=round(amount, 2),
            unit="UZS",
            caption=(
                f"Доля расходов: {round((amount / expense_total) * 100, 1)}%"
                if expense_total > 0
                else None
            ),
        )
        for index, (label, amount) in enumerate(top_expense_categories, start=1)
    ]

    recent_expense_items = [
        DashboardTableItemSchema(
            key=_to_label(row.get("key")),
            label=f"{_to_label(row.get('label'))} • {_to_label(row.get('expense_label'))}",
            value=round(_to_float(row.get("amount")), 2),
            unit="UZS",
            caption=_to_label(row.get("category_label")),
        )
        for row in expense_rows[:8]
    ]

    alerts: list[DashboardAlertSchema] = []
    if revenue_total > 0 and financial_result < 0:
        alerts.append(
            DashboardAlertSchema(
                key="module_financial_result_negative",
                level="warning",
                title="Отдел работает в минус",
                message="Расходы оказались выше собственной выручки за период.",
                value=round(abs(financial_result), 2),
                unit="UZS",
            )
        )

    top_category_amount = top_expense_categories[0][1] if top_expense_categories else 0.0
    if expense_total > 0 and (top_category_amount / expense_total) >= 0.6:
        top_category_label = top_expense_categories[0][0]
        alerts.append(
            DashboardAlertSchema(
                key="module_expense_concentration",
                level="warning",
                title="Расходы сосредоточены в одной категории",
                message=f"Категория «{top_category_label}» занимает слишком большую долю расходов.",
                value=round((top_category_amount / expense_total) * 100, 1),
                unit="%",
            )
        )

    if cash_balance < 0:
        alerts.append(
            DashboardAlertSchema(
                key="module_cash_balance_negative",
                level="critical",
                title="Касса ушла в минус",
                message="Баланс касс отдела стал отрицательным.",
                value=round(abs(cash_balance), 2),
                unit="UZS",
            )
        )

    return ModuleFinanceAnalytics(
        metrics=[
            _metric(key="total_expenses", label="Расходы", value=expense_total, unit="UZS"),
            _signed_metric(key="financial_result", label="Финрезультат", value=financial_result, unit="UZS"),
            _signed_metric(key="net_cashflow", label="Денежный поток", value=net_cashflow, unit="UZS"),
            _signed_metric(key="cash_balance", label="Касса сейчас", value=cash_balance, unit="UZS"),
        ],
        charts=[finance_overview_chart, expense_categories_chart],
        tables=[
            DashboardTableSchema(
                key=f"{module_prefix}_expense_categories_table",
                title="Главные категории расходов",
                description="Какие статьи расходов сильнее всего влияют на деньги отдела.",
                items=expense_category_items,
            ),
            DashboardTableSchema(
                key=f"{module_prefix}_cash_accounts",
                title="Кассы отдела",
                description="Текущий баланс по кассам и счётам внутри отдела.",
                items=_table_items_from_rows(cash_account_rows),
            ),
            DashboardTableSchema(
                key=f"{module_prefix}_recent_expenses",
                title="Последние расходы",
                description="Последние расходные операции за выбранный период.",
                items=recent_expense_items,
            ),
        ],
        alerts=alerts,
    )


def _client_label_sql(alias: str) -> str:
    return (
        f"COALESCE("
        f"NULLIF({alias}.company_name, ''), "
        f"NULLIF(BTRIM(CONCAT_WS(' ', {alias}.first_name, {alias}.last_name)), ''), "
        f"NULLIF({alias}.client_code, ''), "
        f"'Клиент'"
        f")"
    )


async def _build_egg_farm_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    egg_daily_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(produced_on, 'YYYY-MM-DD') AS label,
            SUM(eggs_collected) AS eggs_collected,
            SUM(eggs_broken) AS eggs_broken,
            SUM(eggs_rejected) AS eggs_rejected,
            SUM(eggs_broken + eggs_rejected) AS eggs_losses,
            SUM(GREATEST(eggs_collected - eggs_broken - eggs_rejected, 0)) AS eggs_net
        FROM egg_production
        WHERE {_date_condition('produced_on')} AND {_department_condition('department_id')}
        GROUP BY produced_on
        ORDER BY produced_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    egg_monthly_rows = await db.fetch(
        f"""
        WITH produced AS (
            SELECT
                DATE_TRUNC('month', produced_on)::date AS month_start,
                SUM(GREATEST(eggs_collected - eggs_broken - eggs_rejected, 0)) AS produced,
                SUM(eggs_broken + eggs_rejected) AS losses
            FROM egg_production
            WHERE {_date_condition('produced_on')} AND {_department_condition('department_id')}
            GROUP BY DATE_TRUNC('month', produced_on)::date
        ),
        shipped AS (
            SELECT
                DATE_TRUNC('month', shipped_on)::date AS month_start,
                SUM(eggs_count) AS shipped
            FROM egg_shipments
            WHERE {_date_condition('shipped_on')} AND {_department_condition('department_id')}
            GROUP BY DATE_TRUNC('month', shipped_on)::date
        )
        SELECT
            TO_CHAR(COALESCE(produced.month_start, shipped.month_start), 'YYYY-MM') AS label,
            COALESCE(produced.produced, 0) AS produced,
            COALESCE(shipped.shipped, 0) AS shipped,
            COALESCE(produced.losses, 0) AS losses
        FROM produced
        FULL OUTER JOIN shipped ON shipped.month_start = produced.month_start
        ORDER BY COALESCE(produced.month_start, shipped.month_start)
        """,
        start_date,
        end_date,
        department_ids,
    )
    egg_destination_rows = await db.fetch(
        f"""
        WITH produced AS (
            SELECT
                TO_CHAR(ep.produced_on, 'YYYY-MM-DD') AS label,
                SUM(GREATEST(ep.eggs_collected - ep.eggs_broken - ep.eggs_rejected, 0)) AS net_output
            FROM egg_production ep
            WHERE {_date_condition('ep.produced_on')} AND {_department_condition('ep.department_id')}
            GROUP BY ep.produced_on
        ),
        shipped AS (
            SELECT
                TO_CHAR(es.shipped_on, 'YYYY-MM-DD') AS label,
                SUM(es.eggs_count) AS client_shipments
            FROM egg_shipments es
            WHERE {_date_condition('es.shipped_on')} AND {_department_condition('es.department_id')}
            GROUP BY es.shipped_on
        ),
        incubation AS (
            SELECT
                TO_CHAR(ib.arrived_on, 'YYYY-MM-DD') AS label,
                SUM(ib.eggs_arrived) AS incubation_transfers
            FROM incubation_batches ib
            INNER JOIN egg_production ep ON ep.id = ib.production_id
            WHERE {_date_condition('ib.arrived_on')} AND {_department_condition('ep.department_id')}
            GROUP BY ib.arrived_on
        )
        SELECT
            COALESCE(produced.label, shipped.label, incubation.label) AS label,
            COALESCE(produced.net_output, 0) AS net_output,
            COALESCE(shipped.client_shipments, 0) AS client_shipments,
            COALESCE(incubation.incubation_transfers, 0) AS incubation_transfers
        FROM produced
        FULL OUTER JOIN shipped ON shipped.label = produced.label
        FULL OUTER JOIN incubation ON incubation.label = COALESCE(produced.label, shipped.label)
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    feed_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(fc.consumed_on, 'YYYY-MM-DD') AS label,
            SUM(fc.quantity) AS feed_quantity
        FROM feed_consumptions fc
        INNER JOIN departments d ON d.id = fc.department_id
        WHERE d.module_key = 'egg' AND {_date_condition('fc.consumed_on')} AND {_department_condition('fc.department_id')}
        GROUP BY fc.consumed_on
        ORDER BY fc.consumed_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    feed_type_rows = await db.fetch(
        f"""
        SELECT
            ft.id::text AS key,
            COALESCE(NULLIF(ft.name, ''), NULLIF(ft.code, ''), 'Корм') AS label,
            SUM(fc.quantity) AS value
        FROM feed_consumptions fc
        INNER JOIN departments d ON d.id = fc.department_id
        INNER JOIN feed_types ft ON ft.id = fc.feed_type_id
        WHERE d.module_key = 'egg' AND {_date_condition('fc.consumed_on')} AND {_department_condition('fc.department_id')}
        GROUP BY ft.id, ft.name, ft.code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    medicine_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(mc.consumed_on, 'YYYY-MM-DD') AS label,
            SUM(mc.quantity) AS medicine_quantity
        FROM medicine_consumptions mc
        INNER JOIN departments d ON d.id = mc.department_id
        WHERE d.module_key = 'egg' AND {_date_condition('mc.consumed_on')} AND {_department_condition('mc.department_id')}
        GROUP BY mc.consumed_on
        ORDER BY mc.consumed_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    shipment_revenue_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(es.shipped_on, 'YYYY-MM-DD') AS label,
            SUM(es.eggs_count) AS quantity,
            SUM(COALESCE(es.unit_price, 0) * es.eggs_count) AS revenue
        FROM egg_shipments es
        WHERE {_date_condition('es.shipped_on')} AND {_department_condition('es.department_id')}
        GROUP BY es.shipped_on
        ORDER BY es.shipped_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    egg_client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(COALESCE(es.unit_price, 0) * es.eggs_count) AS value,
            CONCAT(
                'Отгружено: ',
                SUM(es.eggs_count)::text,
                ' шт • Ср. цена: ',
                ROUND(SUM(COALESCE(es.unit_price, 0) * es.eggs_count) / NULLIF(SUM(es.eggs_count), 0), 2)::text,
                ' UZS'
            ) AS caption
        FROM egg_shipments es
        INNER JOIN clients c ON c.id = es.client_id
        WHERE {_date_condition('es.shipped_on')} AND {_department_condition('es.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    egg_client_count = await db.fetchrow(
        f"""
        SELECT COUNT(DISTINCT client_id) AS value
        FROM egg_shipments
        WHERE {_date_condition('shipped_on')} AND {_department_condition('department_id')}
        """,
        start_date,
        end_date,
        department_ids,
    )
    stock_row = await db.fetchrow(
        """
        SELECT
            COALESCE(
                SUM(
                    CASE
                        WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in') THEN sm.quantity
                        ELSE -sm.quantity
                    END
                ),
                0
            ) AS value
        FROM stock_movements sm
        INNER JOIN egg_production ep ON sm.item_key = ('egg:' || CAST(ep.id AS TEXT))
        WHERE sm.item_type = 'egg'
          AND ($1::date IS NULL OR sm.occurred_on <= $1::date)
          AND ($2::uuid[] IS NULL OR ep.department_id = ANY($2::uuid[]))
        """,
        end_date,
        department_ids,
    )
    eggs_collected_total = _sum_rows(egg_daily_rows, "eggs_collected")
    eggs_losses_total = _sum_rows(egg_daily_rows, "eggs_losses")
    sales_volume_total = _sum_rows(shipment_revenue_rows, "quantity")
    sales_revenue_total = _sum_rows(shipment_revenue_rows, "revenue")
    incubation_transfer_total = _sum_rows(egg_destination_rows, "incubation_transfers")
    current_stock_total = _to_float(stock_row["value"]) if stock_row is not None else 0.0
    egg_destination_rows_summary = [
        {
            "key": "client_shipments",
            "label": "Клиентам",
            "value": sales_volume_total,
            "unit": "шт",
            "caption": "Отгружено покупателям за выбранный период",
        },
        {
            "key": "incubation_transfers",
            "label": "В инкубацию",
            "value": incubation_transfer_total,
            "unit": "шт",
            "caption": "Передано из маточника в инкубационный контур",
        },
        {
            "key": "current_stock",
            "label": "Остаток на конец периода",
            "value": current_stock_total,
            "unit": "шт",
            "caption": "Складской остаток яиц на дату окончания периода",
        },
        {
            "key": "losses",
            "label": "Потери",
            "value": eggs_losses_total,
            "unit": "шт",
            "caption": "Битые и отбракованные яйца",
        },
    ]

    charts = [
        DashboardChartSchema(
            key="egg_output_daily",
            title="Выход яиц по дням",
            description="Суточная динамика собранных, списанных и чистых яиц.",
            type="line",
            unit="шт",
            series=_wide_series(
                egg_daily_rows,
                ("collected", "Собрано", "eggs_collected"),
                ("broken", "Битые", "eggs_broken"),
                ("rejected", "Отбраковка", "eggs_rejected"),
                ("net", "Чистый выход", "eggs_net"),
            ),
        ),
        DashboardChartSchema(
            key="egg_monthly_flow",
            title="Месячная динамика",
            description="Сравнение производства, отгрузки и потерь по месяцам.",
            type="line",
            unit="шт",
            series=_wide_series(
                egg_monthly_rows,
                ("produced", "Произведено", "produced"),
                ("shipped", "Отгружено", "shipped"),
                ("losses", "Потери", "losses"),
            ),
        ),
        DashboardChartSchema(
            key="egg_destination_flow",
            title="Куда уходят яйца",
            description="Чистый выпуск, клиентские отгрузки и передача в инкубацию по дням.",
            type="line",
            unit="шт",
            series=_wide_series(
                egg_destination_rows,
                ("net_output", "Чистый выпуск", "net_output"),
                ("client_shipments", "Клиентам", "client_shipments"),
                ("incubation_transfers", "В инкубацию", "incubation_transfers"),
            ),
        ),
        DashboardChartSchema(
            key="egg_loss_rate",
            title="Процент потерь",
            description="Какая доля собранных яиц ушла в потери по дням.",
            type="line",
            unit="%",
            series=_percentage_series(
                egg_daily_rows,
                ("loss_rate", "Потери", "eggs_losses", "eggs_collected"),
            ),
        ),
        DashboardChartSchema(
            key="farm_feed_supply",
            title="Расход корма",
            description="Фактическое потребление корма по дням внутри маточника.",
            type="line",
            unit="кг",
            series=_wide_series(feed_rows, ("feed", "Корм", "feed_quantity")),
        ),
        DashboardChartSchema(
            key="farm_medicine_usage",
            title="Расход лекарств",
            description="Списания лекарств по дням из операций фермы.",
            type="line",
            unit="ед.",
            series=_wide_series(medicine_rows, ("medicine", "Лекарства", "medicine_quantity")),
        ),
        DashboardChartSchema(
            key="egg_revenue_daily",
            title="Выручка по яйцам",
            description="Сколько денег принесли клиентские отгрузки по дням.",
            type="line",
            unit="UZS",
            series=_wide_series(shipment_revenue_rows, ("revenue", "Выручка", "revenue")),
        ),
    ]

    return DashboardSectionSchema(
        key="egg_farm",
        title="Маточник",
        description="Яйценоскость, кормовое обеспечение, расход лекарств и клиентские отгрузки.",
        metrics=[
            _metric(key="net_eggs", label="Чистый выход яиц", value=_sum_rows(egg_daily_rows, "eggs_net"), unit="шт"),
            _metric(key="loss_rate", label="Потери", value=_ratio(eggs_losses_total, eggs_collected_total), unit="%"),
            _metric(key="eggs_to_incubation", label="Передано в инкубацию", value=incubation_transfer_total, unit="шт"),
            _metric(key="current_stock", label="Остаток на конец периода", value=current_stock_total, unit="шт"),
            _metric(key="feed_consumed", label="Корма израсходовано", value=_sum_rows(feed_rows, "feed_quantity"), unit="кг"),
            _metric(key="medicine_used", label="Лекарств израсходовано", value=_sum_rows(medicine_rows, "medicine_quantity"), unit="ед."),
            _metric(key="sales_volume", label="Продано клиентам", value=sales_volume_total, unit="шт"),
            _metric(key="sales_revenue", label="Выручка", value=sales_revenue_total, unit="UZS"),
            _metric(
                key="avg_sale_price",
                label="Средняя цена",
                value=_average_unit_price(sales_revenue_total, sales_volume_total),
                unit="UZS",
            ),
            _metric(
                key="client_base",
                label="Активная база клиентов",
                value=_to_float(egg_client_count["value"]) if egg_client_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=charts,
        breakdowns=[
            DashboardBreakdownSchema(
                key="egg_clients",
                title="Выручка по клиентам",
                description="Какие клиенты дают основную выручку по яйцам.",
                items=_breakdown_items(egg_client_rows, unit="UZS"),
            ),
            DashboardBreakdownSchema(
                key="egg_feed_types",
                title="Структура расхода корма",
                description="Какие типы корма больше всего потребляются в маточнике.",
                items=_breakdown_items(feed_type_rows, unit="кг"),
            ),
            DashboardBreakdownSchema(
                key="egg_destination_balance",
                title="Баланс движения яиц",
                description="Куда уходит выпуск маточника: клиенты, инкубация, потери и остаток.",
                items=_breakdown_items(egg_destination_rows_summary),
            ),
        ],
    )


async def _build_incubation_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    batch_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(ib.arrived_on, 'YYYY-MM-DD') AS label,
            SUM(ib.eggs_arrived) AS eggs_arrived
        FROM incubation_batches ib
        INNER JOIN departments d ON d.id = ib.department_id
        WHERE d.module_key = 'incubation' AND {_date_condition('ib.arrived_on')} AND {_department_condition('ib.department_id')}
        GROUP BY ib.arrived_on
        ORDER BY ib.arrived_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    run_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(COALESCE(ir.end_date, ir.start_date), 'YYYY-MM-DD') AS label,
            SUM(ir.grade_1_count) AS grade_1_count,
            SUM(ir.grade_2_count) AS grade_2_count,
            SUM(ir.bad_eggs_count) AS bad_eggs_count,
            SUM(ir.grade_1_count + ir.grade_2_count + ir.bad_eggs_count) AS eggs_sorted,
            SUM(ir.chicks_hatched) AS chicks_hatched
        FROM incubation_runs ir
        INNER JOIN departments d ON d.id = ir.department_id
        WHERE d.module_key = 'incubation' AND {_date_condition('COALESCE(ir.end_date, ir.start_date)')} AND {_department_condition('ir.department_id')}
        GROUP BY COALESCE(ir.end_date, ir.start_date)
        ORDER BY COALESCE(ir.end_date, ir.start_date)
        """,
        start_date,
        end_date,
        department_ids,
    )
    shipment_revenue_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(cs.shipped_on, 'YYYY-MM-DD') AS label,
            SUM(cs.chicks_count) AS quantity,
            SUM(COALESCE(cs.unit_price, 0) * cs.chicks_count) AS revenue
        FROM chick_shipments cs
        INNER JOIN departments d ON d.id = cs.department_id
        WHERE d.module_key = 'incubation' AND {_date_condition('cs.shipped_on')} AND {_department_condition('cs.department_id')}
        GROUP BY cs.shipped_on
        ORDER BY cs.shipped_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    shipment_client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(COALESCE(cs.unit_price, 0) * cs.chicks_count) AS value,
            CONCAT(
                'Отгружено: ',
                SUM(cs.chicks_count)::text,
                ' шт • Ср. цена: ',
                ROUND(SUM(COALESCE(cs.unit_price, 0) * cs.chicks_count) / NULLIF(SUM(cs.chicks_count), 0), 2)::text,
                ' UZS'
            ) AS caption
        FROM chick_shipments cs
        INNER JOIN departments d ON d.id = cs.department_id
        INNER JOIN clients c ON c.id = cs.client_id
        WHERE d.module_key = 'incubation' AND {_date_condition('cs.shipped_on')} AND {_department_condition('cs.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    source_client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(ib.eggs_arrived) AS value
        FROM incubation_batches ib
        INNER JOIN departments d ON d.id = ib.department_id
        INNER JOIN clients c ON c.id = ib.source_client_id
        WHERE d.module_key = 'incubation' AND {_date_condition('ib.arrived_on')} AND {_department_condition('ib.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_base_count = await db.fetchrow(
        f"""
        SELECT COUNT(DISTINCT client_id) AS value
        FROM (
            SELECT ib.source_client_id AS client_id
            FROM incubation_batches ib
            INNER JOIN departments d ON d.id = ib.department_id
            WHERE d.module_key = 'incubation' AND ib.source_client_id IS NOT NULL AND {_date_condition('ib.arrived_on')} AND {_department_condition('ib.department_id')}

            UNION

            SELECT cs.client_id AS client_id
            FROM chick_shipments cs
            INNER JOIN departments d ON d.id = cs.department_id
            WHERE d.module_key = 'incubation' AND cs.client_id IS NOT NULL AND {_date_condition('cs.shipped_on')} AND {_department_condition('cs.department_id')}
        ) AS incubation_clients
        """,
        start_date,
        end_date,
        department_ids,
    )
    sorted_eggs_total = _sum_rows(run_rows, "eggs_sorted")
    sales_volume_total = _sum_rows(shipment_revenue_rows, "quantity")
    sales_revenue_total = _sum_rows(shipment_revenue_rows, "revenue")

    return DashboardSectionSchema(
        key="incubation",
        title="Инкубация",
        description="Приход яиц, сортировка, вывод птенцов и работа с клиентской базой.",
        metrics=[
            _metric(key="eggs_arrived", label="Яиц поступило", value=_sum_rows(batch_rows, "eggs_arrived"), unit="шт"),
            _metric(key="grade_1_total", label="Сорт 1", value=_sum_rows(run_rows, "grade_1_count"), unit="шт"),
            _metric(key="grade_1_share", label="Доля сорта 1", value=_ratio(_sum_rows(run_rows, "grade_1_count"), sorted_eggs_total), unit="%"),
            _metric(key="grade_2_total", label="Сорт 2", value=_sum_rows(run_rows, "grade_2_count"), unit="шт"),
            _metric(key="bad_eggs_total", label="Брак", value=_sum_rows(run_rows, "bad_eggs_count"), unit="шт"),
            _metric(key="chicks_hatched", label="Птенцов выведено", value=_sum_rows(run_rows, "chicks_hatched"), unit="шт"),
            _metric(key="hatch_rate", label="Выводимость", value=_ratio(_sum_rows(run_rows, "chicks_hatched"), sorted_eggs_total), unit="%"),
            _metric(key="sales_volume", label="Продано птенцов", value=sales_volume_total, unit="шт"),
            _metric(key="sales_revenue", label="Выручка", value=sales_revenue_total, unit="UZS"),
            _metric(
                key="avg_sale_price",
                label="Средняя цена",
                value=_average_unit_price(sales_revenue_total, sales_volume_total),
                unit="UZS",
            ),
            _metric(
                key="client_base",
                label="Клиентская база",
                value=_to_float(client_base_count["value"]) if client_base_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="incubation_egg_arrivals",
                title="Приход яиц",
                description="Сколько яиц пришло в инкубационные партии по дням.",
                type="line",
                unit="шт",
                series=_wide_series(batch_rows, ("eggs_arrived", "Яйца", "eggs_arrived")),
            ),
            DashboardChartSchema(
                key="incubation_quality",
                title="Сортировка по качеству",
                description="Разделение на сорт 1, сорт 2 и брак по завершённым прогонам.",
                type="stacked-bar",
                unit="шт",
                series=_wide_series(
                    run_rows,
                    ("grade_1", "Сорт 1", "grade_1_count"),
                    ("grade_2", "Сорт 2", "grade_2_count"),
                    ("bad", "Брак", "bad_eggs_count"),
                ),
            ),
            DashboardChartSchema(
                key="incubation_hatch",
                title="Выход птенцов",
                description="Сколько птенцов вышло из яиц по датам завершения прогонов.",
                type="line",
                unit="шт",
                series=_wide_series(run_rows, ("chicks", "Птенцы", "chicks_hatched")),
            ),
            DashboardChartSchema(
                key="incubation_revenue",
                title="Выручка по птенцам",
                description="Сколько денег приносят отгрузки птенцов по дням.",
                type="line",
                unit="UZS",
                series=_wide_series(shipment_revenue_rows, ("revenue", "Выручка", "revenue")),
            ),
            DashboardChartSchema(
                key="incubation_yield",
                title="Процент выхода и качества",
                description="Выводимость и доля первого сорта по завершённым прогонам.",
                type="line",
                unit="%",
                series=_percentage_series(
                    run_rows,
                    ("hatch_rate", "Выводимость", "chicks_hatched", "eggs_sorted"),
                    ("grade_1_share", "Сорт 1", "grade_1_count", "eggs_sorted"),
                ),
            ),
        ],
        breakdowns=[
            DashboardBreakdownSchema(
                key="incubation_sources",
                title="База поставщиков яиц",
                description="Источники инкубационных партий.",
                items=_breakdown_items(source_client_rows, unit="шт"),
            ),
            DashboardBreakdownSchema(
                key="incubation_clients",
                title="Выручка по птенцам",
                description="Какие клиенты приносят основную выручку по птенцам.",
                items=_breakdown_items(shipment_client_rows, unit="UZS"),
            ),
        ],
    )


async def _build_factory_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    chick_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(ca.arrived_on, 'YYYY-MM-DD') AS label,
            SUM(ca.chicks_count) AS chicks_count
        FROM chick_arrivals ca
        INNER JOIN departments d ON d.id = ca.department_id
        WHERE d.module_key = 'factory' AND {_date_condition('ca.arrived_on')} AND {_department_condition('ca.department_id')}
        GROUP BY ca.arrived_on
        ORDER BY ca.arrived_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    feed_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(fa.arrived_on, 'YYYY-MM-DD') AS label,
            COALESCE(ft.code, 'unknown') AS series_key,
            COALESCE(ft.name, 'Без типа') AS series_label,
            SUM(fa.quantity) AS value
        FROM feed_arrivals fa
        INNER JOIN departments d ON d.id = fa.department_id
        LEFT JOIN feed_types ft ON ft.id = fa.feed_type_id
        WHERE d.module_key = 'factory' AND {_date_condition('fa.arrived_on')} AND {_department_condition('fa.department_id')}
        GROUP BY fa.arrived_on, ft.code, ft.name
        ORDER BY fa.arrived_on, ft.name
        """,
        start_date,
        end_date,
        department_ids,
    )
    medicine_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(ma.arrived_on, 'YYYY-MM-DD') AS label,
            COALESCE(mt.code, 'unknown') AS series_key,
            COALESCE(mt.name, 'Без типа') AS series_label,
            SUM(ma.quantity) AS value
        FROM medicine_arrivals ma
        INNER JOIN departments d ON d.id = ma.department_id
        LEFT JOIN medicine_types mt ON mt.id = ma.medicine_type_id
        WHERE d.module_key = 'factory' AND {_date_condition('ma.arrived_on')} AND {_department_condition('ma.department_id')}
        GROUP BY ma.arrived_on, mt.code, mt.name
        ORDER BY ma.arrived_on, mt.name
        """,
        start_date,
        end_date,
        department_ids,
    )
    source_client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(ca.chicks_count) AS value
        FROM chick_arrivals ca
        INNER JOIN departments d ON d.id = ca.department_id
        INNER JOIN clients c ON c.id = ca.source_client_id
        WHERE d.module_key = 'factory' AND {_date_condition('ca.arrived_on')} AND {_department_condition('ca.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_base_count = await db.fetchrow(
        f"""
        SELECT COUNT(DISTINCT ca.source_client_id) AS value
        FROM chick_arrivals ca
        INNER JOIN departments d ON d.id = ca.department_id
        WHERE d.module_key = 'factory' AND ca.source_client_id IS NOT NULL AND {_date_condition('ca.arrived_on')} AND {_department_condition('ca.department_id')}
        """,
        start_date,
        end_date,
        department_ids,
    )

    return DashboardSectionSchema(
        key="factory",
        title="Фабрика",
        description="Поступление птенцов, кормов, лекарств и работа с клиентской базой фабрики.",
        metrics=[
            _metric(key="chicks_arrived", label="Птенцов поступило", value=_sum_rows(chick_rows, "chicks_count"), unit="шт"),
            _metric(key="feed_arrived", label="Корма поступило", value=_sum_rows(feed_rows, "value"), unit="кг"),
            _metric(key="medicine_arrived", label="Лекарств поступило", value=_sum_rows(medicine_rows, "value"), unit="ед."),
            _metric(
                key="client_base",
                label="Клиентская база",
                value=_to_float(client_base_count["value"]) if client_base_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="factory_chicks",
                title="Поступление птенцов",
                description="Сколько птенцов пришло на фабрику по дням.",
                type="line",
                unit="шт",
                series=_wide_series(chick_rows, ("chicks", "Птенцы", "chicks_count")),
            ),
            DashboardChartSchema(
                key="factory_feed_types",
                title="Корма по типам",
                description="Разные кормы для разных птиц в разрезе дней.",
                type="stacked-bar",
                unit="кг",
                series=_category_series(feed_rows),
            ),
            DashboardChartSchema(
                key="factory_medicine_types",
                title="Лекарства по типам",
                description="Поступление лекарств с разрезом по видам.",
                type="stacked-bar",
                unit="ед.",
                series=_category_series(medicine_rows),
            ),
        ],
        breakdowns=[
            DashboardBreakdownSchema(
                key="factory_clients",
                title="Клиентская база фабрики",
                description="Основные контрагенты по приходу птенцов.",
                items=_breakdown_items(source_client_rows, unit="шт"),
            )
        ],
    )


async def _build_feed_mill_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    raw_flow_rows = await db.fetch(
        f"""
        WITH arrivals AS (
            SELECT TO_CHAR(fra.arrived_on, 'YYYY-MM-DD') AS label, SUM(fra.quantity) AS arrivals
            FROM feed_raw_arrivals fra
            INNER JOIN departments d ON d.id = fra.department_id
            WHERE d.module_key = 'feed' AND {_date_condition('fra.arrived_on')} AND {_department_condition('fra.department_id')}
            GROUP BY fra.arrived_on
        ),
        consumptions AS (
            SELECT TO_CHAR(frc.consumed_on, 'YYYY-MM-DD') AS label, SUM(frc.quantity) AS consumptions
            FROM feed_raw_consumptions frc
            INNER JOIN departments d ON d.id = frc.department_id
            WHERE d.module_key = 'feed' AND {_date_condition('frc.consumed_on')} AND {_department_condition('frc.department_id')}
            GROUP BY frc.consumed_on
        )
        SELECT
            COALESCE(arrivals.label, consumptions.label) AS label,
            COALESCE(arrivals.arrivals, 0) AS raw_arrivals,
            COALESCE(consumptions.consumptions, 0) AS raw_consumptions
        FROM arrivals
        FULL OUTER JOIN consumptions ON consumptions.label = arrivals.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    product_flow_rows = await db.fetch(
        f"""
        WITH production AS (
            SELECT TO_CHAR(COALESCE(fpb.finished_on, fpb.started_on), 'YYYY-MM-DD') AS label, SUM(fpb.actual_output) AS output
            FROM feed_production_batches fpb
            INNER JOIN departments d ON d.id = fpb.department_id
            WHERE d.module_key = 'feed' AND {_date_condition('COALESCE(fpb.finished_on, fpb.started_on)')} AND {_department_condition('fpb.department_id')}
            GROUP BY COALESCE(fpb.finished_on, fpb.started_on)
        ),
        shipments AS (
            SELECT TO_CHAR(fps.shipped_on, 'YYYY-MM-DD') AS label, SUM(fps.quantity) AS shipment
            FROM feed_product_shipments fps
            INNER JOIN departments d ON d.id = fps.department_id
            WHERE d.module_key = 'feed' AND {_date_condition('fps.shipped_on')} AND {_department_condition('fps.department_id')}
            GROUP BY fps.shipped_on
        )
        SELECT
            COALESCE(production.label, shipments.label) AS label,
            COALESCE(production.output, 0) AS output,
            COALESCE(shipments.shipment, 0) AS shipment
        FROM production
        FULL OUTER JOIN shipments ON shipments.label = production.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    ingredient_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(frc.consumed_on, 'YYYY-MM-DD') AS label,
            COALESCE(fi.code, 'unknown') AS series_key,
            COALESCE(fi.name, 'Без названия') AS series_label,
            SUM(frc.quantity) AS value
        FROM feed_raw_consumptions frc
        INNER JOIN departments d ON d.id = frc.department_id
        LEFT JOIN feed_ingredients fi ON fi.id = frc.ingredient_id
        WHERE d.module_key = 'feed' AND {_date_condition('frc.consumed_on')} AND {_department_condition('frc.department_id')}
        GROUP BY frc.consumed_on, fi.code, fi.name
        ORDER BY frc.consumed_on, fi.name
        """,
        start_date,
        end_date,
        department_ids,
    )
    formula_rows = await db.fetch(
        f"""
        SELECT
            ff.id::text AS key,
            COALESCE(ff.name, ff.code, 'Формула') AS label,
            SUM(fpb.actual_output) AS value
        FROM feed_production_batches fpb
        INNER JOIN departments d ON d.id = fpb.department_id
        INNER JOIN feed_formulas ff ON ff.id = fpb.formula_id
        WHERE d.module_key = 'feed' AND {_date_condition('COALESCE(fpb.finished_on, fpb.started_on)')} AND {_department_condition('fpb.department_id')}
        GROUP BY ff.id, ff.name, ff.code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(COALESCE(fps.unit_price, 0) * fps.quantity) AS value,
            CONCAT(
                'Отгружено: ',
                ROUND(SUM(fps.quantity), 3)::text,
                ' кг • Ср. цена: ',
                ROUND(SUM(COALESCE(fps.unit_price, 0) * fps.quantity) / NULLIF(SUM(fps.quantity), 0), 2)::text,
                ' UZS'
            ) AS caption
        FROM feed_product_shipments fps
        INNER JOIN departments d ON d.id = fps.department_id
        INNER JOIN clients c ON c.id = fps.client_id
        WHERE d.module_key = 'feed' AND {_date_condition('fps.shipped_on')} AND {_department_condition('fps.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_base_count = await db.fetchrow(
        f"""
        WITH active_clients AS (
            SELECT fra.supplier_client_id AS client_id
            FROM feed_raw_arrivals fra
            INNER JOIN departments d ON d.id = fra.department_id
            WHERE d.module_key = 'feed'
              AND fra.supplier_client_id IS NOT NULL
              AND {_date_condition('fra.arrived_on')}
              AND {_department_condition('fra.department_id')}

            UNION

            SELECT fps.client_id AS client_id
            FROM feed_product_shipments fps
            INNER JOIN departments d ON d.id = fps.department_id
            WHERE d.module_key = 'feed'
              AND fps.client_id IS NOT NULL
              AND {_date_condition('fps.shipped_on')}
              AND {_department_condition('fps.department_id')}
        )
        SELECT COUNT(*) AS value
        FROM active_clients
        """,
        start_date,
        end_date,
        department_ids,
    )
    output_total = _sum_rows(product_flow_rows, "output")
    shipment_total = _sum_rows(product_flow_rows, "shipment")
    sales_revenue_row = await db.fetchrow(
        f"""
        SELECT SUM(COALESCE(fps.unit_price, 0) * fps.quantity) AS revenue
        FROM feed_product_shipments fps
        INNER JOIN departments d ON d.id = fps.department_id
        WHERE d.module_key = 'feed' AND {_date_condition('fps.shipped_on')} AND {_department_condition('fps.department_id')}
        """,
        start_date,
        end_date,
        department_ids,
    )
    revenue_by_day_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(fps.shipped_on, 'YYYY-MM-DD') AS label,
            SUM(COALESCE(fps.unit_price, 0) * fps.quantity) AS revenue
        FROM feed_product_shipments fps
        INNER JOIN departments d ON d.id = fps.department_id
        WHERE d.module_key = 'feed' AND {_date_condition('fps.shipped_on')} AND {_department_condition('fps.department_id')}
        GROUP BY fps.shipped_on
        ORDER BY fps.shipped_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    sales_revenue_total = _to_float(sales_revenue_row["revenue"]) if sales_revenue_row is not None else 0.0

    return DashboardSectionSchema(
        key="feed_mill",
        title="Корма завод",
        description="Сырьё, комбинация ингредиентов, выпуск продукта и клиентская база.",
        metrics=[
            _metric(key="raw_arrivals", label="Сырья пришло", value=_sum_rows(raw_flow_rows, "raw_arrivals"), unit="кг"),
            _metric(key="raw_consumptions", label="Сырья израсходовано", value=_sum_rows(raw_flow_rows, "raw_consumptions"), unit="кг"),
            _metric(key="product_output", label="Готового корма выпущено", value=_sum_rows(product_flow_rows, "output"), unit="кг"),
            _metric(key="sales_volume", label="Продано продукта", value=shipment_total, unit="кг"),
            _metric(key="sales_revenue", label="Выручка", value=sales_revenue_total, unit="UZS"),
            _metric(
                key="avg_sale_price",
                label="Средняя цена",
                value=_average_unit_price(sales_revenue_total, shipment_total),
                unit="UZS",
            ),
            _metric(key="shipment_rate", label="Реализация выпуска", value=_ratio(shipment_total, output_total), unit="%"),
            _metric(
                key="client_base",
                label="Клиентская база",
                value=_to_float(client_base_count["value"]) if client_base_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="feed_raw_flow",
                title="Сырьё: приход и расход",
                description="Динамика поступления и потребления сырья.",
                type="line",
                unit="кг",
                series=_wide_series(
                    raw_flow_rows,
                    ("arrivals", "Приход", "raw_arrivals"),
                    ("consumptions", "Расход", "raw_consumptions"),
                ),
            ),
            DashboardChartSchema(
                key="feed_product_flow",
                title="Продукт: выпуск и отгрузка",
                description="Сколько комбикорма произведено и сколько ушло клиентам.",
                type="line",
                unit="кг",
                series=_wide_series(
                    product_flow_rows,
                    ("output", "Выпуск", "output"),
                    ("shipment", "Отгрузка", "shipment"),
                ),
            ),
            DashboardChartSchema(
                key="feed_shipment_rate",
                title="Реализация выпуска в процентах",
                description="Какая доля произведённого корма ушла клиентам.",
                type="line",
                unit="%",
                series=_percentage_series(
                    product_flow_rows,
                    ("shipment_rate", "Отгрузка от выпуска", "shipment", "output"),
                ),
            ),
            DashboardChartSchema(
                key="feed_revenue",
                title="Выручка по продукту",
                description="Сколько денег принесли клиентские отгрузки готового корма.",
                type="line",
                unit="UZS",
                series=_wide_series(revenue_by_day_rows, ("revenue", "Выручка", "revenue")),
            ),
            DashboardChartSchema(
                key="feed_ingredient_mix",
                title="Комбинация сырья",
                description="Структура расхода ингредиентов по дням.",
                type="stacked-bar",
                unit="кг",
                series=_category_series(ingredient_rows),
            ),
        ],
        breakdowns=[
            DashboardBreakdownSchema(
                key="feed_formulas",
                title="Продукт и формулы",
                description="Какие формулы дают основной выпуск готового продукта.",
                items=_breakdown_items(formula_rows, unit="кг"),
            ),
            DashboardBreakdownSchema(
                key="feed_clients",
                title="Выручка по клиентам",
                description="Какие клиенты приносят основную выручку по готовому корму.",
                items=_breakdown_items(client_rows, unit="UZS"),
            ),
        ],
    )


async def _build_vet_pharmacy_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    flow_rows = await db.fetch(
        f"""
        WITH arrivals AS (
            SELECT TO_CHAR(ma.arrived_on, 'YYYY-MM-DD') AS label, SUM(ma.quantity) AS arrivals
            FROM medicine_arrivals ma
            INNER JOIN departments d ON d.id = ma.department_id
            WHERE d.module_key = 'medicine' AND {_date_condition('ma.arrived_on')} AND {_department_condition('ma.department_id')}
            GROUP BY ma.arrived_on
        ),
        consumptions AS (
            SELECT TO_CHAR(mc.consumed_on, 'YYYY-MM-DD') AS label, SUM(mc.quantity) AS consumptions
            FROM medicine_consumptions mc
            INNER JOIN departments d ON d.id = mc.department_id
            WHERE d.module_key = 'medicine' AND {_date_condition('mc.consumed_on')} AND {_department_condition('mc.department_id')}
            GROUP BY mc.consumed_on
        )
        SELECT
            COALESCE(arrivals.label, consumptions.label) AS label,
            COALESCE(arrivals.arrivals, 0) AS arrivals,
            COALESCE(consumptions.consumptions, 0) AS consumptions
        FROM arrivals
        FULL OUTER JOIN consumptions ON consumptions.label = arrivals.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    stock_rows = await db.fetch(
        f"""
        SELECT
            COALESCE(mt.name, 'Без названия') AS label,
            SUM(mb.remaining_quantity) AS stock
        FROM medicine_batches mb
        INNER JOIN departments d ON d.id = mb.department_id
        LEFT JOIN medicine_types mt ON mt.id = mb.medicine_type_id
        WHERE d.module_key = 'medicine' AND {_date_condition('mb.arrived_on')} AND {_department_condition('mb.department_id')}
        GROUP BY mt.name
        ORDER BY stock DESC, label
        """,
        start_date,
        end_date,
        department_ids,
    )
    expiry_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(expiry_date, 'YYYY-MM') AS label,
            SUM(remaining_quantity) AS stock
        FROM medicine_batches
        INNER JOIN departments d ON d.id = medicine_batches.department_id
        WHERE expiry_date IS NOT NULL AND d.module_key = 'medicine' AND {_date_condition('medicine_batches.arrived_on')} AND {_department_condition('medicine_batches.department_id')}
        GROUP BY TO_CHAR(expiry_date, 'YYYY-MM')
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    expiring_batch_rows = await db.fetch(
        f"""
        SELECT
            mb.id::text AS key,
            COALESCE(mt.name, 'Без названия') AS label,
            mb.remaining_quantity AS value,
            CONCAT(
                COALESCE(NULLIF(mb.barcode, ''), 'без штрихкода'),
                ' • ',
                COALESCE(TO_CHAR(mb.expiry_date, 'YYYY-MM-DD'), 'без срока')
            ) AS caption,
            mb.unit AS unit
        FROM medicine_batches mb
        INNER JOIN departments d ON d.id = mb.department_id
        LEFT JOIN medicine_types mt ON mt.id = mb.medicine_type_id
        WHERE d.module_key = 'medicine' AND mb.remaining_quantity > 0 AND {_date_condition('mb.arrived_on')} AND {_department_condition('mb.department_id')}
        ORDER BY mb.expiry_date NULLS LAST, mb.remaining_quantity DESC
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    supplier_rows = await db.fetch(
        f"""
        WITH active_clients AS (
            SELECT
                ma.supplier_client_id AS client_id,
                SUM(ma.quantity) AS arrivals_qty,
                0::numeric AS consumptions_qty
            FROM medicine_arrivals ma
            INNER JOIN departments d ON d.id = ma.department_id
            WHERE d.module_key = 'medicine'
              AND ma.supplier_client_id IS NOT NULL
              AND {_date_condition('ma.arrived_on')}
              AND {_department_condition('ma.department_id')}
            GROUP BY ma.supplier_client_id

            UNION ALL

            SELECT
                mc.client_id AS client_id,
                0::numeric AS arrivals_qty,
                SUM(mc.quantity) AS consumptions_qty
            FROM medicine_consumptions mc
            INNER JOIN departments d ON d.id = mc.department_id
            WHERE d.module_key = 'medicine'
              AND mc.client_id IS NOT NULL
              AND {_date_condition('mc.consumed_on')}
              AND {_department_condition('mc.department_id')}
            GROUP BY mc.client_id
        )
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(active_clients.arrivals_qty + active_clients.consumptions_qty) AS value,
            'ед.' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • роль: ',
                CASE
                    WHEN SUM(active_clients.arrivals_qty) > 0 AND SUM(active_clients.consumptions_qty) > 0
                    THEN 'поставщик и получатель'
                    WHEN SUM(active_clients.arrivals_qty) > 0
                    THEN 'поставщик'
                    ELSE 'получатель'
                END,
                ' • приход: ',
                ROUND(SUM(active_clients.arrivals_qty), 3)::text,
                ' ед. • расход: ',
                ROUND(SUM(active_clients.consumptions_qty), 3)::text,
                ' ед.'
            ) AS caption
        FROM active_clients
        INNER JOIN clients c ON c.id = active_clients.client_id
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_base_count = await db.fetchrow(
        f"""
        WITH active_clients AS (
            SELECT ma.supplier_client_id AS client_id
            FROM medicine_arrivals ma
            INNER JOIN departments d ON d.id = ma.department_id
            WHERE d.module_key = 'medicine'
              AND ma.supplier_client_id IS NOT NULL
              AND {_date_condition('ma.arrived_on')}
              AND {_department_condition('ma.department_id')}

            UNION

            SELECT mc.client_id AS client_id
            FROM medicine_consumptions mc
            INNER JOIN departments d ON d.id = mc.department_id
            WHERE d.module_key = 'medicine'
              AND mc.client_id IS NOT NULL
              AND {_date_condition('mc.consumed_on')}
              AND {_department_condition('mc.department_id')}
        )
        SELECT COUNT(*) AS value
        FROM active_clients
        """,
        start_date,
        end_date,
        department_ids,
    )

    return DashboardSectionSchema(
        key="vet_pharmacy",
        title="Вет аптека",
        description="Приход и уход лекарств, клиентская база, штрихкоды и сроки годности партий.",
        metrics=[
            _metric(key="arrivals", label="Лекарств пришло", value=_sum_rows(flow_rows, "arrivals"), unit="ед."),
            _metric(key="consumptions", label="Лекарств ушло", value=_sum_rows(flow_rows, "consumptions"), unit="ед."),
            _metric(key="turnover_rate", label="Оборачиваемость", value=_ratio(_sum_rows(flow_rows, "consumptions"), _sum_rows(flow_rows, "arrivals")), unit="%"),
            _metric(key="stock", label="Остаток на складе", value=_sum_rows(stock_rows, "stock"), unit="ед."),
            _metric(
                key="client_base",
                label="Клиентская база",
                value=_to_float(client_base_count["value"]) if client_base_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="medicine_flow",
                title="Приход и расход лекарств",
                description="Операционная динамика движения лекарств.",
                type="line",
                unit="ед.",
                series=_wide_series(
                    flow_rows,
                    ("arrivals", "Приход", "arrivals"),
                    ("consumptions", "Расход", "consumptions"),
                ),
            ),
            DashboardChartSchema(
                key="medicine_stock",
                title="Остатки по типам",
                description="Что сейчас лежит на складе вет аптеки.",
                type="line",
                unit="ед.",
                series=_wide_series(stock_rows, ("stock", "Остаток", "stock")),
            ),
            DashboardChartSchema(
                key="medicine_expiry",
                title="Остатки по срокам годности",
                description="Какие объёмы привязаны к ближайшим expiry периодам.",
                type="line",
                unit="ед.",
                series=_wide_series(expiry_rows, ("stock", "Остаток", "stock")),
            ),
            DashboardChartSchema(
                key="medicine_turnover_rate",
                title="Оборачиваемость лекарств",
                description="Какая доля входящего объёма уже выдана в расход.",
                type="line",
                unit="%",
                series=_percentage_series(
                    flow_rows,
                    ("turnover_rate", "Оборачиваемость", "consumptions", "arrivals"),
                ),
            ),
        ],
        breakdowns=[
            DashboardBreakdownSchema(
                key="medicine_suppliers",
                title="Клиентская база",
                description="Активные контрагенты по приходу и расходу лекарств.",
                items=_breakdown_items(supplier_rows, unit="ед."),
            ),
            DashboardBreakdownSchema(
                key="medicine_batches",
                title="Штрихкод и срок годности",
                description="Партии лекарств с кодом и сроком действия.",
                items=_breakdown_items(expiring_batch_rows),
            ),
        ],
    )


async def _build_slaughterhouse_section(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardSectionSchema:
    flow_rows = await db.fetch(
        f"""
        WITH arrivals AS (
            SELECT TO_CHAR(sa.arrived_on, 'YYYY-MM-DD') AS label, SUM(sa.birds_count) AS arrivals
            FROM slaughter_arrivals sa
            INNER JOIN departments d ON d.id = sa.department_id
            WHERE d.module_key = 'slaughter' AND {_date_condition('sa.arrived_on')} AND {_department_condition('sa.department_id')}
            GROUP BY sa.arrived_on
        ),
        processed AS (
            SELECT TO_CHAR(sp.processed_on, 'YYYY-MM-DD') AS label, SUM(sp.birds_processed) AS processed
            FROM slaughter_processings sp
            INNER JOIN departments d ON d.id = sp.department_id
            WHERE d.module_key = 'slaughter' AND {_date_condition('sp.processed_on')} AND {_department_condition('sp.department_id')}
            GROUP BY sp.processed_on
        )
        SELECT
            COALESCE(arrivals.label, processed.label) AS label,
            COALESCE(arrivals.arrivals, 0) AS arrivals,
            COALESCE(processed.processed, 0) AS processed
        FROM arrivals
        FULL OUTER JOIN processed ON processed.label = arrivals.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    quality_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(sp.processed_on, 'YYYY-MM-DD') AS label,
            SUM(sp.first_sort_count) AS first_sort_count,
            SUM(sp.second_sort_count) AS second_sort_count,
            SUM(sp.bad_count) AS bad_count
            ,
            SUM(sp.first_sort_count + sp.second_sort_count + sp.bad_count) AS total_sorted
        FROM slaughter_processings sp
        INNER JOIN departments d ON d.id = sp.department_id
        WHERE d.module_key = 'slaughter' AND {_date_condition('sp.processed_on')} AND {_department_condition('sp.department_id')}
        GROUP BY sp.processed_on
        ORDER BY sp.processed_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    semi_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(ssp.produced_on, 'YYYY-MM-DD') AS label,
            COALESCE(NULLIF(ssp.part_name, ''), NULLIF(ssp.code, ''), 'Без названия') AS series_key,
            COALESCE(NULLIF(ssp.part_name, ''), NULLIF(ssp.code, ''), 'Без названия') AS series_label,
            SUM(ssp.quantity) AS value
        FROM slaughter_semi_products ssp
        INNER JOIN departments d ON d.id = ssp.department_id
        WHERE d.module_key = 'slaughter' AND {_date_condition('ssp.produced_on')} AND {_department_condition('ssp.department_id')}
        GROUP BY ssp.produced_on, ssp.part_name, ssp.code
        ORDER BY ssp.produced_on, series_label
        """,
        start_date,
        end_date,
        department_ids,
    )
    semi_total_rows = await db.fetch(
        f"""
        SELECT
            COALESCE(NULLIF(ssp.part_name, ''), NULLIF(ssp.code, ''), 'Без названия') AS key,
            COALESCE(NULLIF(ssp.part_name, ''), NULLIF(ssp.code, ''), 'Без названия') AS label,
            SUM(ssp.quantity) AS value
        FROM slaughter_semi_products ssp
        INNER JOIN departments d ON d.id = ssp.department_id
        WHERE d.module_key = 'slaughter' AND {_date_condition('ssp.produced_on')} AND {_department_condition('ssp.department_id')}
        GROUP BY ssp.part_name, ssp.code
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(COALESCE(ss.unit_price, 0) * ss.quantity) AS value,
            CONCAT(
                'Отгружено: ',
                ROUND(SUM(ss.quantity), 3)::text,
                ' кг • Ср. цена: ',
                ROUND(SUM(COALESCE(ss.unit_price, 0) * ss.quantity) / NULLIF(SUM(ss.quantity), 0), 2)::text,
                ' UZS'
            ) AS caption
        FROM slaughter_semi_product_shipments ss
        INNER JOIN departments d ON d.id = ss.department_id
        INNER JOIN clients c ON c.id = ss.client_id
        WHERE d.module_key = 'slaughter' AND {_date_condition('ss.shipped_on')} AND {_department_condition('ss.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 6
        """,
        start_date,
        end_date,
        department_ids,
    )
    revenue_rows = await db.fetch(
        f"""
        SELECT
            TO_CHAR(ss.shipped_on, 'YYYY-MM-DD') AS label,
            SUM(ss.quantity) AS quantity,
            SUM(COALESCE(ss.unit_price, 0) * ss.quantity) AS revenue
        FROM slaughter_semi_product_shipments ss
        INNER JOIN departments d ON d.id = ss.department_id
        WHERE d.module_key = 'slaughter' AND {_date_condition('ss.shipped_on')} AND {_department_condition('ss.department_id')}
        GROUP BY ss.shipped_on
        ORDER BY ss.shipped_on
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_base_count = await db.fetchrow(
        f"""
        WITH active_clients AS (
            SELECT sa.supplier_client_id AS client_id
            FROM slaughter_arrivals sa
            INNER JOIN departments d ON d.id = sa.department_id
            WHERE d.module_key = 'slaughter'
              AND sa.supplier_client_id IS NOT NULL
              AND {_date_condition('sa.arrived_on')}
              AND {_department_condition('sa.department_id')}

            UNION

            SELECT ss.client_id AS client_id
            FROM slaughter_semi_product_shipments ss
            INNER JOIN departments d ON d.id = ss.department_id
            WHERE d.module_key = 'slaughter'
              AND ss.client_id IS NOT NULL
              AND {_date_condition('ss.shipped_on')}
              AND {_department_condition('ss.department_id')}
        )
        SELECT COUNT(*) AS value
        FROM active_clients
        """,
        start_date,
        end_date,
        department_ids,
    )
    arrivals_total = _sum_rows(flow_rows, "arrivals")
    processed_total = _sum_rows(flow_rows, "processed")
    total_sorted = _sum_rows(quality_rows, "total_sorted")
    sales_volume_total = _sum_rows(revenue_rows, "quantity")
    sales_revenue_total = _sum_rows(revenue_rows, "revenue")

    return DashboardSectionSchema(
        key="slaughterhouse",
        title="Убойня",
        description="Приход птицы, первый и второй сорт, разделка по частям, полуфабрикат и клиентская база.",
        metrics=[
            _metric(key="arrivals", label="Птицы поступило", value=_sum_rows(flow_rows, "arrivals"), unit="шт"),
            _metric(key="processed", label="Птицы обработано", value=_sum_rows(flow_rows, "processed"), unit="шт"),
            _metric(key="process_rate", label="Переработано", value=_ratio(processed_total, arrivals_total), unit="%"),
            _metric(key="first_sort_total", label="Первый сорт", value=_sum_rows(quality_rows, "first_sort_count"), unit="шт"),
            _metric(key="first_sort_share", label="Доля первого сорта", value=_ratio(_sum_rows(quality_rows, "first_sort_count"), total_sorted), unit="%"),
            _metric(key="second_sort_total", label="Второй сорт", value=_sum_rows(quality_rows, "second_sort_count"), unit="шт"),
            _metric(key="bad_total", label="Брак / плохой", value=_sum_rows(quality_rows, "bad_count"), unit="шт"),
            _metric(key="semi_products", label="Полуфабриката произведено", value=_sum_rows(semi_rows, "value"), unit="кг"),
            _metric(key="sales_volume", label="Продано полуфабриката", value=sales_volume_total, unit="кг"),
            _metric(key="sales_revenue", label="Выручка", value=sales_revenue_total, unit="UZS"),
            _metric(
                key="avg_sale_price",
                label="Средняя цена",
                value=_average_unit_price(sales_revenue_total, sales_volume_total),
                unit="UZS",
            ),
            _metric(
                key="client_base",
                label="Клиентская база",
                value=_to_float(client_base_count["value"]) if client_base_count is not None else 0.0,
                unit="клиентов",
            ),
        ],
        charts=[
            DashboardChartSchema(
                key="slaughter_flow",
                title="Приход и разделка",
                description="Сравнение входящего потока и переработки по дням.",
                type="line",
                unit="шт",
                series=_wide_series(
                    flow_rows,
                    ("arrivals", "Приход", "arrivals"),
                    ("processed", "Разделка", "processed"),
                ),
            ),
            DashboardChartSchema(
                key="slaughter_quality",
                title="Первый сорт, второй сорт и брак",
                description="Структура качества после переработки.",
                type="stacked-bar",
                unit="шт",
                series=_wide_series(
                    quality_rows,
                    ("first", "Первый сорт", "first_sort_count"),
                    ("second", "Второй сорт", "second_sort_count"),
                    ("bad", "Брак", "bad_count"),
                ),
            ),
            DashboardChartSchema(
                key="slaughter_semi_products",
                title="Разделка по частям",
                description="Какие части птицы выходят после разделки по дням.",
                type="stacked-bar",
                unit="кг",
                series=_category_series(semi_rows),
            ),
            DashboardChartSchema(
                key="slaughter_process_rate",
                title="Процент переработки",
                description="Какая доля входящего потока птицы была переработана.",
                type="line",
                unit="%",
                series=_percentage_series(
                    flow_rows,
                    ("process_rate", "Переработка", "processed", "arrivals"),
                ),
            ),
            DashboardChartSchema(
                key="slaughter_revenue",
                title="Выручка по полуфабрикату",
                description="Сколько денег приносят отгрузки полуфабриката по дням.",
                type="line",
                unit="UZS",
                series=_wide_series(revenue_rows, ("revenue", "Выручка", "revenue")),
            ),
        ],
        breakdowns=[
            DashboardBreakdownSchema(
                key="slaughter_parts",
                title="Полуфабрикат и части",
                description="Самые востребованные части и партии полуфабриката.",
                items=_breakdown_items(semi_total_rows, unit="кг"),
            ),
            DashboardBreakdownSchema(
                key="slaughter_clients",
                title="Выручка по клиентам",
                description="Какие клиенты приносят основную выручку по полуфабрикату.",
                items=_breakdown_items(client_rows, unit="UZS"),
            )
        ],
    )


def _metric_map(section: DashboardSectionSchema) -> dict[str, DashboardMetricSchema]:
    return {metric.key: metric for metric in section.metrics}


def _chart_map(section: DashboardSectionSchema) -> dict[str, DashboardChartSchema]:
    return {chart.key: chart for chart in section.charts}


def _breakdown_map(section: DashboardSectionSchema) -> dict[str, DashboardBreakdownSchema]:
    return {breakdown.key: breakdown for breakdown in section.breakdowns}


def _metric_from(
    metrics: dict[str, DashboardMetricSchema],
    source_key: str,
    *,
    key: str,
    label: str,
    unit: str | None = None,
    value: float | None = None,
) -> DashboardMetricSchema:
    source = metrics.get(source_key)
    resolved_value = source.value if source is not None and value is None else (value or 0.0)
    resolved_unit = unit if unit is not None else (source.unit if source is not None else None)
    return _metric(key=key, label=label, value=resolved_value, unit=resolved_unit)


def _table_items_from_rows(rows, *, default_unit: str | None = None) -> list[DashboardTableItemSchema]:
    items: list[DashboardTableItemSchema] = []
    for row in rows:
        items.append(
            DashboardTableItemSchema(
                key=_to_label(row["key"]),
                label=_to_label(row["label"]),
                value=_to_float(row["value"]),
                unit=_to_label(row["unit"]) if "unit" in row and row["unit"] is not None else default_unit,
                caption=_to_label(row["caption"]) if "caption" in row and row["caption"] is not None else None,
            )
        )
    return items


def _table_from_breakdown(
    breakdown: DashboardBreakdownSchema | None,
    *,
    key: str,
    title: str,
    description: str | None = None,
) -> DashboardTableSchema:
    if breakdown is None:
        return DashboardTableSchema(key=key, title=title, description=description, items=[])

    return DashboardTableSchema(
        key=key,
        title=title,
        description=description or breakdown.description,
        items=[
            DashboardTableItemSchema(
                key=item.key,
                label=item.label,
                value=item.value,
                unit=item.unit,
                caption=item.caption,
            )
            for item in breakdown.items
        ],
    )


def _chart_copy(charts: dict[str, DashboardChartSchema], key: str) -> DashboardChartSchema | None:
    chart = charts.get(key)
    if chart is None:
        return None
    return chart.model_copy(deep=True)


def _department_label(row: dict[str, object] | None) -> str:
    if row is None:
        return ""
    for key in ("name", "code", "id"):
        value = _to_label(row.get(key) if isinstance(row, dict) else None).strip()
        if value and value != "—":
            return value
    return ""


async def _resolve_department_scope(
    db: Database,
    department_id: UUID | None,
    *,
    organization_id: str,
    start_date: date | None,
    end_date: date | None,
) -> tuple[list[UUID] | None, DashboardOverviewScopeSchema]:
    if department_id is None:
        department_rows = await db.fetch(
            """
            SELECT id
            FROM departments
            WHERE organization_id = $1
              AND is_active = true
            """,
            organization_id,
        )
        return [row["id"] for row in department_rows], DashboardOverviewScopeSchema(
            departmentId=None,
            departmentLabel="Все отделы",
            departmentModuleKey=None,
            departmentPath=[],
            startDate=start_date,
            endDate=end_date,
        )

    selected_department = await db.fetchrow(
        """
        SELECT id, name, code, module_key
        FROM departments
        WHERE id = $1
          AND organization_id = $2
        LIMIT 1
        """,
        str(department_id),
        organization_id,
    )
    if selected_department is None:
        raise HTTPException(status_code=404, detail="Department not found")

    scope_rows = await db.fetch(
        """
        WITH RECURSIVE department_scope AS (
            SELECT id
            FROM departments
            WHERE id = $1::uuid
              AND organization_id = $2
            UNION ALL
            SELECT d.id
            FROM departments d
            INNER JOIN department_scope ds ON ds.id = d.parent_department_id
            WHERE d.organization_id = $2
        )
        SELECT id
        FROM department_scope
        """,
        str(department_id),
        organization_id,
    )
    department_ids = [row["id"] for row in scope_rows]

    path_rows = await db.fetch(
        """
        WITH RECURSIVE department_path AS (
            SELECT id, name, code, parent_department_id, 0 AS depth
            FROM departments
            WHERE id = $1::uuid
              AND organization_id = $2

            UNION ALL

            SELECT d.id, d.name, d.code, d.parent_department_id, dp.depth + 1
            FROM departments d
            INNER JOIN department_path dp ON dp.parent_department_id = d.id
            WHERE d.organization_id = $2
        )
        SELECT id, name, code, depth
        FROM department_path
        ORDER BY depth DESC
        """,
        str(department_id),
        organization_id,
    )
    department_path = [
        _department_label(dict(row))
        for row in path_rows
        if _department_label(dict(row))
    ]

    selected_data = dict(selected_department)
    return department_ids, DashboardOverviewScopeSchema(
        departmentId=str(selected_department["id"]),
        departmentLabel=_department_label(selected_data),
        departmentModuleKey=_to_label(selected_data.get("module_key")) if selected_data.get("module_key") is not None else None,
        departmentPath=department_path,
        startDate=start_date,
        endDate=end_date,
    )


async def _build_egg_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_egg_farm_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="egg",
        module_prefix="egg",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    recent_shipments_rows = await db.fetch(
        f"""
        SELECT
            es.id::text AS key,
            CONCAT(TO_CHAR(es.shipped_on, 'YYYY-MM-DD'), ' • ', {_client_label_sql('c')}) AS label,
            es.eggs_count AS value,
            CONCAT('Выручка: ', ROUND(COALESCE(es.unit_price, 0) * es.eggs_count, 2)::text, ' UZS') AS caption
        FROM egg_shipments es
        INNER JOIN clients c ON c.id = es.client_id
        WHERE {_date_condition('es.shipped_on')} AND {_department_condition('es.department_id')}
        ORDER BY es.shipped_on DESC, es.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_registry_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            COUNT(es.id) AS value,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                CASE
                    WHEN NULLIF(c.company_name, '') IS NOT NULL THEN CONCAT(' • ', c.company_name)
                    ELSE ''
                END
            ) AS caption
        FROM egg_shipments es
        INNER JOIN clients c ON c.id = es.client_id
        WHERE {_date_condition('es.shipped_on')} AND {_department_condition('es.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    loss_rate = metrics.get("loss_rate").value if metrics.get("loss_rate") is not None else 0.0
    alerts: list[DashboardAlertSchema] = []
    if loss_rate >= 12:
        alerts.append(
            DashboardAlertSchema(
                key="egg_loss_rate_critical",
                level="critical",
                title="Высокий процент потерь",
                message="Потери яиц превысили критический порог.",
                value=loss_rate,
                unit="%",
            )
        )
    elif loss_rate >= 7:
        alerts.append(
            DashboardAlertSchema(
                key="egg_loss_rate_warning",
                level="warning",
                title="Рост потерь яиц",
                message="Потери выше целевого операционного уровня.",
                value=loss_rate,
                unit="%",
            )
        )

    selected_charts = [
        _chart_copy(charts, "egg_output_daily"),
        _chart_copy(charts, "egg_monthly_flow"),
        _chart_copy(charts, "egg_destination_flow"),
        _chart_copy(charts, "egg_loss_rate"),
        _chart_copy(charts, "farm_feed_supply"),
        _chart_copy(charts, "farm_medicine_usage"),
        _chart_copy(charts, "egg_revenue_daily"),
    ]

    module = DashboardModuleSchema(
        key="egg_farm",
        title="Маточник",
        description="Операционный контур маточника: выпуск, потери, отгрузка и ключевые ресурсы.",
        kpis=[
            _metric_from(metrics, "net_eggs", key="net_eggs", label="Чистый выпуск яиц"),
            _metric_from(metrics, "current_stock", key="current_stock", label="Остаток яиц", unit="шт"),
            _metric_from(metrics, "loss_rate", key="loss_rate", label="Процент потерь", unit="%"),
            _metric_from(metrics, "sales_volume", key="shipment_volume", label="Объём отгрузки", unit="шт"),
            _metric_from(
                metrics,
                "eggs_to_incubation",
                key="eggs_to_incubation",
                label="Передано в инкубацию",
                unit="шт",
            ),
            _metric_from(metrics, "sales_revenue", key="egg_revenue", label="Выручка от яиц", unit="UZS"),
            _metric_from(metrics, "feed_consumed", key="feed_consumed", label="Расход корма", unit="кг"),
            _metric_from(metrics, "medicine_used", key="medicine_consumed", label="Расход лекарств", unit="ед."),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("egg_clients"),
                key="egg_clients",
                title="Выручка по клиентам",
                description="Какие клиенты дают основную выручку по яйцам.",
            ),
            _table_from_breakdown(
                breakdowns.get("egg_destination_balance"),
                key="egg_destination_balance",
                title="Баланс движения яиц",
                description="Куда уходит выпуск маточника внутри выбранного периода.",
            ),
            _table_from_breakdown(
                breakdowns.get("egg_feed_types"),
                key="egg_feed_types",
                title="Структура расхода корма",
                description="Какие типы корма больше всего потребляются в маточнике.",
            ),
            DashboardTableSchema(
                key="egg_client_registry",
                title="Активная клиентская база",
                description="Клиенты, которые реально участвовали в отгрузках яиц за период.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            DashboardTableSchema(
                key="egg_recent_shipments",
                title="Последние отгрузки",
                description="Последние операции отгрузки яиц клиентам.",
                items=_table_items_from_rows(recent_shipments_rows, default_unit="шт"),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )
    return module


async def _build_incubation_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_incubation_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="incubation",
        module_prefix="incubation",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    eggs_set_row = await db.fetchrow(
        f"""
        SELECT SUM(ir.eggs_set) AS value
        FROM incubation_runs ir
        INNER JOIN departments d ON d.id = ir.department_id
        WHERE d.module_key = 'incubation'
          AND {_date_condition('COALESCE(ir.end_date, ir.start_date)')}
          AND {_department_condition('ir.department_id')}
        """,
        start_date,
        end_date,
        department_ids,
    )
    eggs_set_total = _to_float(eggs_set_row["value"]) if eggs_set_row is not None else 0.0

    dispatched_row = await db.fetchrow(
        f"""
        WITH transfers AS (
            SELECT SUM(ca.chicks_count) AS qty
            FROM chick_arrivals ca
            INNER JOIN incubation_runs ir ON ir.id = ca.run_id
            INNER JOIN departments d ON d.id = ir.department_id
            WHERE d.module_key = 'incubation'
              AND {_date_condition('ca.arrived_on')}
              AND {_department_condition('ir.department_id')}
        ),
        shipments AS (
            SELECT SUM(cs.chicks_count) AS qty
            FROM chick_shipments cs
            INNER JOIN departments d ON d.id = cs.department_id
            WHERE d.module_key = 'incubation'
              AND {_date_condition('cs.shipped_on')}
              AND {_department_condition('cs.department_id')}
        )
        SELECT COALESCE(transfers.qty, 0) + COALESCE(shipments.qty, 0) AS value
        FROM transfers, shipments
        """,
        start_date,
        end_date,
        department_ids,
    )
    dispatched_total = _to_float(dispatched_row["value"]) if dispatched_row is not None else 0.0

    client_registry_rows = await db.fetch(
        f"""
        WITH active_clients AS (
            SELECT
                ib.source_client_id AS client_id,
                COUNT(*) AS source_batches,
                SUM(ib.eggs_arrived) AS eggs_arrived,
                0 AS shipments_count,
                0 AS chicks_shipped
            FROM incubation_batches ib
            INNER JOIN departments d ON d.id = ib.department_id
            WHERE d.module_key = 'incubation'
              AND ib.source_client_id IS NOT NULL
              AND {_date_condition('ib.arrived_on')}
              AND {_department_condition('ib.department_id')}
            GROUP BY ib.source_client_id

            UNION ALL

            SELECT
                cs.client_id AS client_id,
                0 AS source_batches,
                0 AS eggs_arrived,
                COUNT(*) AS shipments_count,
                SUM(cs.chicks_count) AS chicks_shipped
            FROM chick_shipments cs
            INNER JOIN departments d ON d.id = cs.department_id
            WHERE d.module_key = 'incubation'
              AND cs.client_id IS NOT NULL
              AND {_date_condition('cs.shipped_on')}
              AND {_department_condition('cs.department_id')}
            GROUP BY cs.client_id
        )
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(active_clients.source_batches + active_clients.shipments_count) AS value,
            'операций' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • роль: ',
                CASE
                    WHEN SUM(active_clients.eggs_arrived) > 0 AND SUM(active_clients.chicks_shipped) > 0 THEN 'поставщик и покупатель'
                    WHEN SUM(active_clients.eggs_arrived) > 0 THEN 'поставщик яиц'
                    ELSE 'покупатель птенцов'
                END,
                ' • яйца: ',
                SUM(active_clients.eggs_arrived)::text,
                ' • птенцы: ',
                SUM(active_clients.chicks_shipped)::text
            ) AS caption
        FROM active_clients
        INNER JOIN clients c ON c.id = active_clients.client_id
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    active_batches_rows = await db.fetch(
        f"""
        SELECT
            ib.id::text AS key,
            COALESCE(NULLIF(ib.batch_code, ''), ib.id::text) AS label,
            ib.eggs_arrived AS value,
            CONCAT(
                'Ожидаемый вывод: ',
                COALESCE(TO_CHAR(ib.expected_hatch_on, 'YYYY-MM-DD'), '—')
            ) AS caption
        FROM incubation_batches ib
        INNER JOIN departments d ON d.id = ib.department_id
        WHERE d.module_key = 'incubation'
          AND {_date_condition('ib.arrived_on')}
          AND {_department_condition('ib.department_id')}
          AND NOT EXISTS (
              SELECT 1
              FROM incubation_runs ir
              WHERE ir.batch_id = ib.id
                AND ir.end_date IS NOT NULL
          )
        ORDER BY ib.expected_hatch_on NULLS LAST, ib.arrived_on DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_dispatch_rows = await db.fetch(
        f"""
        WITH transfers AS (
            SELECT
                ca.id::text AS key,
                CONCAT(TO_CHAR(ca.arrived_on, 'YYYY-MM-DD'), ' • Передача на фабрику') AS label,
                ca.chicks_count AS value,
                CONCAT('run: ', COALESCE(ir.id::text, '—')) AS caption,
                ca.arrived_on AS event_date
            FROM chick_arrivals ca
            INNER JOIN incubation_runs ir ON ir.id = ca.run_id
            INNER JOIN departments d ON d.id = ir.department_id
            WHERE d.module_key = 'incubation'
              AND {_date_condition('ca.arrived_on')}
              AND {_department_condition('ir.department_id')}
        ),
        shipments AS (
            SELECT
                cs.id::text AS key,
                CONCAT(TO_CHAR(cs.shipped_on, 'YYYY-MM-DD'), ' • Отгрузка клиенту') AS label,
                cs.chicks_count AS value,
                CONCAT('Счёт: ', COALESCE(NULLIF(cs.invoice_no, ''), '—')) AS caption,
                cs.shipped_on AS event_date
            FROM chick_shipments cs
            INNER JOIN departments d ON d.id = cs.department_id
            WHERE d.module_key = 'incubation'
              AND {_date_condition('cs.shipped_on')}
              AND {_department_condition('cs.department_id')}
        )
        SELECT key, label, value, caption
        FROM (
            SELECT key, label, value, caption, event_date FROM transfers
            UNION ALL
            SELECT key, label, value, caption, event_date FROM shipments
        ) flow
        ORDER BY event_date DESC, key
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    hatch_rate = metrics.get("hatch_rate").value if metrics.get("hatch_rate") is not None else 0.0
    alerts: list[DashboardAlertSchema] = []
    if hatch_rate < 70:
        alerts.append(
            DashboardAlertSchema(
                key="incubation_hatch_rate_critical",
                level="critical",
                title="Низкая выводимость",
                message="Hatch rate ниже целевого уровня.",
                value=hatch_rate,
                unit="%",
            )
        )
    elif hatch_rate < 82:
        alerts.append(
            DashboardAlertSchema(
                key="incubation_hatch_rate_warning",
                level="warning",
                title="Снижение hatch rate",
                message="Нужно проверить качество партии и режим инкубации.",
                value=hatch_rate,
                unit="%",
            )
        )

    selected_charts = [
        _chart_copy(charts, "incubation_egg_arrivals"),
        _chart_copy(charts, "incubation_quality"),
        _chart_copy(charts, "incubation_hatch"),
        _chart_copy(charts, "incubation_yield"),
        _chart_copy(charts, "incubation_revenue"),
    ]

    module = DashboardModuleSchema(
        key="incubation",
        title="Инкубация",
        description="Поток партий, вывод птенцов и передача результата дальше по цепочке.",
        kpis=[
            _metric_from(metrics, "eggs_arrived", key="eggs_arrived", label="Яиц пришло", unit="шт"),
            _metric_from(metrics, "chicks_hatched", key="chicks_hatched", label="Птенцов вывелось", unit="шт"),
            _metric_from(metrics, "hatch_rate", key="hatch_rate", label="Hatch rate", unit="%"),
            _metric_from(metrics, "bad_eggs_total", key="bad_eggs", label="Bad eggs", unit="шт"),
            _metric_from(metrics, "sales_volume", key="chicks_dispatched", label="Передано/отгружено", unit="шт", value=dispatched_total),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            _metric_from(metrics, "grade_1_total", key="grade_1_total", label="Сорт 1", unit="шт"),
            _metric_from(metrics, "grade_2_total", key="grade_2_total", label="Сорт 2", unit="шт"),
            _metric_from(metrics, "grade_1_total", key="eggs_set", label="Яиц заложено", unit="шт", value=eggs_set_total),
            _metric_from(metrics, "sales_revenue", key="sales_revenue", label="Выручка от птенцов", unit="UZS"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("incubation_clients"),
                key="incubation_clients",
                title="Клиенты по птенцам",
                description="Какие клиенты дают основной сбыт и выручку по выведенным птенцам.",
            ),
            _table_from_breakdown(
                breakdowns.get("incubation_sources"),
                key="incubation_sources",
                title="Источники яиц",
                description="Какие клиенты формируют входящий поток яиц в инкубацию.",
            ),
            DashboardTableSchema(
                key="incubation_client_registry",
                title="Активная клиентская база",
                description="Партнёры, участвующие в поставках яиц и отгрузках птенцов за период.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            DashboardTableSchema(
                key="incubation_active_batches",
                title="Активные партии",
                description="Партии без завершённого инкубационного цикла.",
                items=_table_items_from_rows(active_batches_rows, default_unit="шт"),
            ),
            DashboardTableSchema(
                key="incubation_recent_dispatch",
                title="Последние передачи / отгрузки",
                description="Куда ушли выведенные птенцы.",
                items=_table_items_from_rows(recent_dispatch_rows, default_unit="шт"),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )
    return module


async def _build_factory_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_factory_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="factory",
        module_prefix="factory",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    chick_flow_rows = await db.fetch(
        f"""
        WITH arrivals AS (
            SELECT TO_CHAR(ca.arrived_on, 'YYYY-MM-DD') AS label, SUM(ca.chicks_count) AS arrivals
            FROM chick_arrivals ca
            INNER JOIN departments d ON d.id = ca.department_id
            WHERE d.module_key = 'factory'
              AND {_date_condition('ca.arrived_on')}
              AND {_department_condition('ca.department_id')}
            GROUP BY ca.arrived_on
        ),
        transfers AS (
            SELECT TO_CHAR(sa.arrived_on, 'YYYY-MM-DD') AS label, SUM(sa.birds_count) AS transferred
            FROM slaughter_arrivals sa
            INNER JOIN chick_arrivals ca ON ca.id = sa.chick_arrival_id
            INNER JOIN departments d ON d.id = ca.department_id
            WHERE d.module_key = 'factory'
              AND {_date_condition('sa.arrived_on')}
              AND {_department_condition('ca.department_id')}
            GROUP BY sa.arrived_on
        )
        SELECT
            COALESCE(arrivals.label, transfers.label) AS label,
            COALESCE(arrivals.arrivals, 0) AS arrivals,
            COALESCE(transfers.transferred, 0) AS transferred
        FROM arrivals
        FULL OUTER JOIN transfers ON transfers.label = arrivals.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    feed_type_rows = await db.fetch(
        f"""
        SELECT
            ft.id::text AS key,
            COALESCE(NULLIF(ft.name, ''), NULLIF(ft.code, ''), 'Корм') AS label,
            SUM(fa.quantity) AS value,
            CONCAT(
                'Типов птицы: ',
                COUNT(DISTINCT fa.poultry_type_id)::text
            ) AS caption
        FROM feed_arrivals fa
        INNER JOIN departments d ON d.id = fa.department_id
        INNER JOIN feed_types ft ON ft.id = fa.feed_type_id
        WHERE d.module_key = 'factory'
          AND {_date_condition('fa.arrived_on')}
          AND {_department_condition('fa.department_id')}
        GROUP BY ft.id, ft.name, ft.code
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    medicine_type_rows = await db.fetch(
        f"""
        SELECT
            mt.id::text AS key,
            COALESCE(NULLIF(mt.name, ''), NULLIF(mt.code, ''), 'Лекарство') AS label,
            SUM(ma.quantity) AS value,
            CONCAT(
                'Типов птицы: ',
                COUNT(DISTINCT ma.poultry_type_id)::text
            ) AS caption
        FROM medicine_arrivals ma
        INNER JOIN departments d ON d.id = ma.department_id
        INNER JOIN medicine_types mt ON mt.id = ma.medicine_type_id
        WHERE d.module_key = 'factory'
          AND {_date_condition('ma.arrived_on')}
          AND {_department_condition('ma.department_id')}
        GROUP BY mt.id, mt.name, mt.code
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    stock_rows = await db.fetch(
        """
        SELECT
            sm.item_type,
            SUM(
                CASE
                    WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in')
                    THEN sm.quantity
                    ELSE -sm.quantity
                END
            ) AS balance
        FROM stock_movements sm
        INNER JOIN departments d ON d.id = sm.department_id
        WHERE d.module_key = 'factory'
          AND ($1::date IS NULL OR sm.occurred_on <= $1::date)
          AND ($2::uuid[] IS NULL OR sm.department_id = ANY($2::uuid[]))
        GROUP BY sm.item_type
        """,
        end_date,
        department_ids,
    )
    stock_map = {str(row["item_type"]): _to_float(row["balance"]) for row in stock_rows}

    critical_stock_row = await db.fetchrow(
        """
        WITH balances AS (
            SELECT
                sm.item_type,
                sm.item_key,
                SUM(
                    CASE
                        WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in')
                        THEN sm.quantity
                        ELSE -sm.quantity
                    END
                ) AS balance
            FROM stock_movements sm
            INNER JOIN departments d ON d.id = sm.department_id
            WHERE d.module_key = 'factory'
              AND ($1::date IS NULL OR sm.occurred_on <= $1::date)
              AND ($2::uuid[] IS NULL OR sm.department_id = ANY($2::uuid[]))
            GROUP BY sm.item_type, sm.item_key
        )
        SELECT COUNT(*) AS value
        FROM balances
        WHERE balance > 0
          AND (
            (item_type = 'chick' AND balance < 500)
            OR (item_type = 'feed' AND balance < 300)
            OR (item_type = 'medicine' AND balance < 50)
          )
        """,
        end_date,
        department_ids,
    )
    critical_stock_items = _to_float(critical_stock_row["value"]) if critical_stock_row is not None else 0.0

    client_registry_rows = await db.fetch(
        f"""
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            COUNT(ca.id) AS value,
            'поставок' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • птенцов: ',
                SUM(ca.chicks_count)::text
            ) AS caption
        FROM chick_arrivals ca
        INNER JOIN departments d ON d.id = ca.department_id
        INNER JOIN clients c ON c.id = ca.source_client_id
        WHERE d.module_key = 'factory'
          AND {_date_condition('ca.arrived_on')}
          AND {_department_condition('ca.department_id')}
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_arrivals_rows = await db.fetch(
        f"""
        SELECT
            ca.id::text AS key,
            CONCAT(TO_CHAR(ca.arrived_on, 'YYYY-MM-DD'), ' • ', {_client_label_sql('c')}) AS label,
            ca.chicks_count AS value,
            CONCAT('run: ', COALESCE(ca.run_id::text, '—')) AS caption
        FROM chick_arrivals ca
        INNER JOIN departments d ON d.id = ca.department_id
        LEFT JOIN clients c ON c.id = ca.source_client_id
        WHERE d.module_key = 'factory'
          AND {_date_condition('ca.arrived_on')}
          AND {_department_condition('ca.department_id')}
        ORDER BY ca.arrived_on DESC, ca.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_transfers_rows = await db.fetch(
        f"""
        SELECT
            sa.id::text AS key,
            CONCAT(TO_CHAR(sa.arrived_on, 'YYYY-MM-DD'), ' • Передача на убойню') AS label,
            sa.birds_count AS value,
            CONCAT('arrival: ', COALESCE(sa.chick_arrival_id::text, '—')) AS caption
        FROM slaughter_arrivals sa
        INNER JOIN chick_arrivals ca ON ca.id = sa.chick_arrival_id
        INNER JOIN departments d ON d.id = ca.department_id
        WHERE d.module_key = 'factory'
          AND {_date_condition('sa.arrived_on')}
          AND {_department_condition('ca.department_id')}
        ORDER BY sa.arrived_on DESC, sa.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    chicks_arrived = _sum_rows(chick_flow_rows, "arrivals")
    sent_to_slaughter = _sum_rows(chick_flow_rows, "transferred")
    chicks_stock = stock_map.get("chick", 0.0)

    alerts: list[DashboardAlertSchema] = []
    if chicks_stock < 500 and chicks_arrived > 0:
        alerts.append(
            DashboardAlertSchema(
                key="factory_low_chick_stock",
                level="warning",
                title="Низкий остаток живого поголовья",
                message="Текущий остаток птенцов ниже операционного минимума.",
                value=chicks_stock,
                unit="шт",
            )
        )
    if critical_stock_items > 0:
        alerts.append(
            DashboardAlertSchema(
                key="factory_critical_stock_items",
                level="warning",
                title="Есть критичные остатки",
                message="Выявлены позиции с критически низким остатком.",
                value=critical_stock_items,
                unit="шт",
            )
        )

    selected_charts = [
        _chart_copy(charts, "factory_chicks"),
        DashboardChartSchema(
            key="factory_chicks_flow",
            title="Приход птенцов и передача на убойню",
            description="Динамика движения живого поголовья.",
            type="line",
            unit="шт",
            series=_wide_series(
                chick_flow_rows,
                ("arrivals", "Приход", "arrivals"),
                ("transferred", "Передано на убойню", "transferred"),
            ),
        ),
        _chart_copy(charts, "factory_feed_types"),
        _chart_copy(charts, "factory_medicine_types"),
    ]

    return DashboardModuleSchema(
        key="factory",
        title="Фабрика",
        description="Приход птенцов, ресурсы выращивания и передача птицы в убойный контур.",
        kpis=[
            _metric_from(metrics, "chicks_arrived", key="chicks_arrived", label="Птенцов пришло", unit="шт"),
            _metric_from(metrics, "feed_arrived", key="feed_arrived", label="Корма пришло", unit="кг"),
            _metric_from(metrics, "medicine_arrived", key="medicine_arrived", label="Лекарств пришло", unit="ед."),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            _metric(key="chicks_stock", label="Текущий остаток поголовья", value=chicks_stock, unit="шт"),
            _metric(key="sent_to_slaughter", label="Передано на убойню", value=sent_to_slaughter, unit="шт"),
            _metric(key="critical_stock_items", label="Критичные остатки", value=critical_stock_items, unit="шт"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("factory_clients"),
                key="factory_clients",
                title="Клиентская база фабрики",
                description="Основные поставщики птенцов в фабричный контур.",
            ),
            DashboardTableSchema(
                key="factory_feed_arrivals_by_type",
                title="Корма по типам",
                description="Какие корма приходят на фабрику и для скольких типов птицы они используются.",
                items=_table_items_from_rows(feed_type_rows, default_unit="кг"),
            ),
            DashboardTableSchema(
                key="factory_medicine_arrivals_by_type",
                title="Лекарства по типам",
                description="Какие лекарства приходят на фабрику и по каким направлениям птицы они используются.",
                items=_table_items_from_rows(medicine_type_rows, default_unit="ед."),
            ),
            DashboardTableSchema(
                key="factory_client_registry",
                title="Активная клиентская база",
                description="Контрагенты, которые реально поставляли птенцов на фабрику за период.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            DashboardTableSchema(
                key="factory_recent_arrivals",
                title="Последние приходы птенцов",
                description="Последние зафиксированные поступления.",
                items=_table_items_from_rows(recent_arrivals_rows, default_unit="шт"),
            ),
            DashboardTableSchema(
                key="factory_recent_transfers",
                title="Последние передачи на убойню",
                description="Движения из фабричного контура в убойню.",
                items=_table_items_from_rows(recent_transfers_rows, default_unit="шт"),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )


async def _build_feed_mill_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_feed_mill_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="feed",
        module_prefix="feed",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    stock_row = await db.fetchrow(
        """
        WITH balances AS (
            SELECT
                sm.item_key,
                SUM(
                    CASE
                        WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in')
                        THEN sm.quantity
                        ELSE -sm.quantity
                    END
                ) AS balance
            FROM stock_movements sm
            INNER JOIN departments d ON d.id = sm.department_id
            WHERE d.module_key = 'feed'
              AND sm.item_type = 'feed'
              AND ($1::date IS NULL OR sm.occurred_on <= $1::date)
              AND ($2::uuid[] IS NULL OR sm.department_id = ANY($2::uuid[]))
            GROUP BY sm.item_key
        )
        SELECT
            COALESCE(SUM(CASE WHEN item_key LIKE 'feed_raw:%' THEN balance ELSE 0 END), 0) AS raw_stock,
            COALESCE(SUM(CASE WHEN item_key LIKE 'feed_product:%' THEN balance ELSE 0 END), 0) AS product_stock
        FROM balances
        """,
        end_date,
        department_ids,
    )
    raw_stock = _to_float(stock_row["raw_stock"]) if stock_row is not None else 0.0
    product_stock = _to_float(stock_row["product_stock"]) if stock_row is not None else 0.0

    low_raw_stock_rows = await db.fetch(
        """
        WITH raw_balances AS (
            SELECT
                split_part(sm.item_key, ':', 2) AS ingredient_id,
                SUM(
                    CASE
                        WHEN sm.movement_kind IN ('incoming', 'transfer_in', 'adjustment_in')
                        THEN sm.quantity
                        ELSE -sm.quantity
                    END
                ) AS balance
            FROM stock_movements sm
            INNER JOIN departments d ON d.id = sm.department_id
            WHERE d.module_key = 'feed'
              AND sm.item_type = 'feed'
              AND sm.item_key LIKE 'feed_raw:%'
              AND ($1::date IS NULL OR sm.occurred_on <= $1::date)
              AND ($2::uuid[] IS NULL OR sm.department_id = ANY($2::uuid[]))
            GROUP BY split_part(sm.item_key, ':', 2)
        )
        SELECT
            COALESCE(fi.id::text, rb.ingredient_id) AS key,
            COALESCE(NULLIF(fi.name, ''), NULLIF(fi.code, ''), 'Ингредиент') AS label,
            rb.balance AS value,
            'Низкий остаток сырья' AS caption
        FROM raw_balances rb
        LEFT JOIN feed_ingredients fi ON fi.id::text = rb.ingredient_id
        WHERE rb.balance <= 300
        ORDER BY rb.balance ASC, label
        LIMIT 8
        """,
        end_date,
        department_ids,
    )
    recent_batches_rows = await db.fetch(
        f"""
        SELECT
            fpb.id::text AS key,
            COALESCE(NULLIF(fpb.batch_code, ''), fpb.id::text) AS label,
            COALESCE(fpb.actual_output, 0) AS value,
            CONCAT(
                'Формула: ',
                COALESCE(NULLIF(ff.name, ''), NULLIF(ff.code, ''), '—'),
                ' • ',
                TO_CHAR(COALESCE(fpb.finished_on, fpb.started_on), 'YYYY-MM-DD')
            ) AS caption
        FROM feed_production_batches fpb
        INNER JOIN departments d ON d.id = fpb.department_id
        LEFT JOIN feed_formulas ff ON ff.id = fpb.formula_id
        WHERE d.module_key = 'feed'
          AND {_date_condition('COALESCE(fpb.finished_on, fpb.started_on)')}
          AND {_department_condition('fpb.department_id')}
        ORDER BY COALESCE(fpb.finished_on, fpb.started_on) DESC, fpb.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_registry_rows = await db.fetch(
        f"""
        WITH active_clients AS (
            SELECT
                fra.supplier_client_id AS client_id,
                COUNT(*) AS raw_arrivals_count,
                SUM(fra.quantity) AS raw_arrivals_qty,
                0::bigint AS shipments_count,
                0::numeric AS shipped_qty
            FROM feed_raw_arrivals fra
            INNER JOIN departments d ON d.id = fra.department_id
            WHERE d.module_key = 'feed'
              AND fra.supplier_client_id IS NOT NULL
              AND {_date_condition('fra.arrived_on')}
              AND {_department_condition('fra.department_id')}
            GROUP BY fra.supplier_client_id

            UNION ALL

            SELECT
                fps.client_id AS client_id,
                0::bigint AS raw_arrivals_count,
                0::numeric AS raw_arrivals_qty,
                COUNT(*) AS shipments_count,
                SUM(fps.quantity) AS shipped_qty
            FROM feed_product_shipments fps
            INNER JOIN departments d ON d.id = fps.department_id
            WHERE d.module_key = 'feed'
              AND fps.client_id IS NOT NULL
              AND {_date_condition('fps.shipped_on')}
              AND {_department_condition('fps.department_id')}
            GROUP BY fps.client_id
        )
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(active_clients.raw_arrivals_count + active_clients.shipments_count) AS value,
            'операций' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • роль: ',
                CASE
                    WHEN SUM(active_clients.raw_arrivals_qty) > 0 AND SUM(active_clients.shipped_qty) > 0
                    THEN 'поставщик и покупатель'
                    WHEN SUM(active_clients.raw_arrivals_qty) > 0
                    THEN 'поставщик сырья'
                    ELSE 'покупатель продукта'
                END,
                ' • сырьё: ',
                ROUND(SUM(active_clients.raw_arrivals_qty), 3)::text,
                ' кг • продукт: ',
                ROUND(SUM(active_clients.shipped_qty), 3)::text,
                ' кг'
            ) AS caption
        FROM active_clients
        INNER JOIN clients c ON c.id = active_clients.client_id
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_shipments_rows = await db.fetch(
        f"""
        SELECT
            fps.id::text AS key,
            CONCAT(TO_CHAR(fps.shipped_on, 'YYYY-MM-DD'), ' • ', {_client_label_sql('c')}) AS label,
            fps.quantity AS value,
            CONCAT(
                'Выручка: ',
                ROUND(COALESCE(fps.unit_price, 0) * fps.quantity, 2)::text,
                ' UZS'
            ) AS caption
        FROM feed_product_shipments fps
        INNER JOIN departments d ON d.id = fps.department_id
        LEFT JOIN clients c ON c.id = fps.client_id
        WHERE d.module_key = 'feed'
          AND {_date_condition('fps.shipped_on')}
          AND {_department_condition('fps.department_id')}
        ORDER BY fps.shipped_on DESC, fps.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    shipment_rate = metrics.get("shipment_rate").value if metrics.get("shipment_rate") is not None else 0.0
    output_value = metrics.get("product_output").value if metrics.get("product_output") is not None else 0.0
    alerts: list[DashboardAlertSchema] = []
    if output_value > 0 and shipment_rate < 65:
        alerts.append(
            DashboardAlertSchema(
                key="feed_shipment_rate_low",
                level="warning",
                title="Низкая реализация выпуска",
                message="Отгрузка готового продукта отстаёт от объёма выпуска.",
                value=shipment_rate,
                unit="%",
            )
        )
    if low_raw_stock_rows:
        alerts.append(
            DashboardAlertSchema(
                key="feed_low_raw_stock",
                level="warning",
                title="Критичные остатки сырья",
                message="Есть ингредиенты с низким остатком.",
                value=float(len(low_raw_stock_rows)),
                unit="шт",
            )
        )

    selected_charts = [
        _chart_copy(charts, "feed_raw_flow"),
        _chart_copy(charts, "feed_product_flow"),
        _chart_copy(charts, "feed_shipment_rate"),
        _chart_copy(charts, "feed_revenue"),
        _chart_copy(charts, "feed_ingredient_mix"),
    ]

    return DashboardModuleSchema(
        key="feed_mill",
        title="Корма завод",
        description="Сырьё, формулы продукта, клиентская база и последние операции кормового производства.",
        kpis=[
            _metric_from(metrics, "raw_arrivals", key="raw_arrivals", label="Приход сырья", unit="кг"),
            _metric_from(metrics, "raw_consumptions", key="raw_consumed", label="Расход сырья", unit="кг"),
            _metric_from(metrics, "product_output", key="product_output", label="Выпуск готового корма", unit="кг"),
            _metric_from(metrics, "sales_volume", key="product_shipped", label="Отгрузка готового продукта", unit="кг"),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            _metric_from(metrics, "sales_revenue", key="sales_revenue", label="Выручка", unit="UZS"),
            _metric(
                key="stock_total",
                label="Текущий остаток сырьё+продукт",
                value=raw_stock + product_stock,
                unit="кг",
            ),
            _metric_from(metrics, "shipment_rate", key="shipment_rate", label="Shipment rate / output utilization", unit="%"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("feed_formulas"),
                key="feed_formulas",
                title="Продукт и формулы",
                description="Какие формулы дают основной выпуск готового продукта.",
            ),
            _table_from_breakdown(
                breakdowns.get("feed_clients"),
                key="feed_clients",
                title="Выручка по клиентам",
                description="Какие клиенты дают основной сбыт и выручку по готовому корму.",
            ),
            DashboardTableSchema(
                key="feed_client_registry",
                title="Активная клиентская база",
                description="Контрагенты, которые участвовали в поставках сырья и отгрузках готового продукта.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            DashboardTableSchema(
                key="feed_low_raw_stock",
                title="Сырьё с низким остатком",
                description="Позиции, которые рискуют остановить выпуск.",
                items=_table_items_from_rows(low_raw_stock_rows, default_unit="кг"),
            ),
            DashboardTableSchema(
                key="feed_recent_batches",
                title="Последние производственные партии",
                description="Последние batch'и выпуска готового корма.",
                items=_table_items_from_rows(recent_batches_rows, default_unit="кг"),
            ),
            DashboardTableSchema(
                key="feed_recent_shipments",
                title="Последние отгрузки продукта",
                description="Последние отгрузки готового корма клиентам.",
                items=_table_items_from_rows(recent_shipments_rows, default_unit="кг"),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )


async def _build_vet_pharmacy_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_vet_pharmacy_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="medicine",
        module_prefix="medicine",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    as_of = end_date or date.today()
    expiry_row = await db.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (
                WHERE mb.remaining_quantity > 0
                  AND mb.expiry_date IS NOT NULL
                  AND mb.expiry_date < $1::date
            ) AS expired_count,
            COUNT(*) FILTER (
                WHERE mb.remaining_quantity > 0
                  AND mb.expiry_date IS NOT NULL
                  AND mb.expiry_date >= $1::date
                  AND mb.expiry_date <= ($1::date + INTERVAL '30 days')
            ) AS expiring_count
        FROM medicine_batches mb
        INNER JOIN departments d ON d.id = mb.department_id
        WHERE d.module_key = 'medicine'
          AND ($2::uuid[] IS NULL OR mb.department_id = ANY($2::uuid[]))
        """,
        as_of,
        department_ids,
    )
    expiring_count = _to_float(expiry_row["expiring_count"]) if expiry_row is not None else 0.0
    expired_count = _to_float(expiry_row["expired_count"]) if expiry_row is not None else 0.0

    latest_consumptions_rows = await db.fetch(
        f"""
        SELECT
            mc.id::text AS key,
            CONCAT(
                TO_CHAR(mc.consumed_on, 'YYYY-MM-DD'),
                ' • ',
                COALESCE(NULLIF(mt.name, ''), NULLIF(mt.code, ''), 'Лекарство')
            ) AS label,
            mc.quantity AS value,
            CONCAT(
                'Партия: ',
                COALESCE(NULLIF(mb.batch_code, ''), mb.id::text),
                ' • ',
                COALESCE(NULLIF(mc.purpose, ''), 'операционное списание')
            ) AS caption,
            mc.unit AS unit
        FROM medicine_consumptions mc
        INNER JOIN departments d ON d.id = mc.department_id
        LEFT JOIN medicine_batches mb ON mb.id = mc.batch_id
        LEFT JOIN medicine_types mt ON mt.id = mb.medicine_type_id
        WHERE d.module_key = 'medicine'
          AND {_date_condition('mc.consumed_on')}
          AND {_department_condition('mc.department_id')}
        ORDER BY mc.consumed_on DESC, mc.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_registry_rows = await db.fetch(
        f"""
        WITH active_clients AS (
            SELECT
                ma.supplier_client_id AS client_id,
                COUNT(*) AS arrivals_count,
                SUM(ma.quantity) AS arrivals_qty,
                0::bigint AS consumptions_count,
                0::numeric AS consumptions_qty
            FROM medicine_arrivals ma
            INNER JOIN departments d ON d.id = ma.department_id
            WHERE d.module_key = 'medicine'
              AND ma.supplier_client_id IS NOT NULL
              AND {_date_condition('ma.arrived_on')}
              AND {_department_condition('ma.department_id')}
            GROUP BY ma.supplier_client_id

            UNION ALL

            SELECT
                mc.client_id AS client_id,
                0::bigint AS arrivals_count,
                0::numeric AS arrivals_qty,
                COUNT(*) AS consumptions_count,
                SUM(mc.quantity) AS consumptions_qty
            FROM medicine_consumptions mc
            INNER JOIN departments d ON d.id = mc.department_id
            WHERE d.module_key = 'medicine'
              AND mc.client_id IS NOT NULL
              AND {_date_condition('mc.consumed_on')}
              AND {_department_condition('mc.department_id')}
            GROUP BY mc.client_id
        )
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(active_clients.arrivals_count + active_clients.consumptions_count) AS value,
            'операций' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • роль: ',
                CASE
                    WHEN SUM(active_clients.arrivals_qty) > 0 AND SUM(active_clients.consumptions_qty) > 0
                    THEN 'поставщик и получатель'
                    WHEN SUM(active_clients.arrivals_qty) > 0
                    THEN 'поставщик'
                    ELSE 'получатель'
                END,
                ' • приход: ',
                ROUND(SUM(active_clients.arrivals_qty), 3)::text,
                ' ед. • расход: ',
                ROUND(SUM(active_clients.consumptions_qty), 3)::text,
                ' ед.'
            ) AS caption
        FROM active_clients
        INNER JOIN clients c ON c.id = active_clients.client_id
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_batches_rows = await db.fetch(
        f"""
        SELECT
            mb.id::text AS key,
            CONCAT(
                TO_CHAR(mb.arrived_on, 'YYYY-MM-DD'),
                ' • ',
                COALESCE(NULLIF(mt.name, ''), NULLIF(mt.code, ''), 'Лекарство')
            ) AS label,
            mb.received_quantity AS value,
            CONCAT(
                'Партия: ',
                COALESCE(NULLIF(mb.batch_code, ''), mb.id::text),
                ' • ',
                COALESCE(NULLIF(mb.barcode, ''), 'без штрихкода'),
                ' • ',
                COALESCE(TO_CHAR(mb.expiry_date, 'YYYY-MM-DD'), 'без срока')
            ) AS caption,
            mb.unit AS unit
        FROM medicine_batches mb
        INNER JOIN departments d ON d.id = mb.department_id
        LEFT JOIN medicine_types mt ON mt.id = mb.medicine_type_id
        WHERE d.module_key = 'medicine'
          AND {_date_condition('mb.arrived_on')}
          AND {_department_condition('mb.department_id')}
        ORDER BY mb.arrived_on DESC, mb.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    turnover_rate = metrics.get("turnover_rate").value if metrics.get("turnover_rate") is not None else 0.0
    alerts: list[DashboardAlertSchema] = []
    if expired_count > 0:
        alerts.append(
            DashboardAlertSchema(
                key="medicine_expired_batches",
                level="critical",
                title="Есть просроченные партии",
                message="На складе есть партии с истекшим сроком годности.",
                value=expired_count,
                unit="шт",
            )
        )
    if expiring_count > 0:
        alerts.append(
            DashboardAlertSchema(
                key="medicine_expiring_batches",
                level="warning",
                title="Партии с близким сроком",
                message="Есть партии, истекающие в ближайшие 30 дней.",
                value=expiring_count,
                unit="шт",
            )
        )
    if turnover_rate < 30 and metrics.get("arrivals", DashboardMetricSchema(key="", label="", value=0)).value > 0:
        alerts.append(
            DashboardAlertSchema(
                key="medicine_turnover_low",
                level="warning",
                title="Низкая оборачиваемость",
                message="Доля расхода существенно ниже входящего объёма.",
                value=turnover_rate,
                unit="%",
            )
        )

    selected_charts = [
        _chart_copy(charts, "medicine_flow"),
        _chart_copy(charts, "medicine_stock"),
        _chart_copy(charts, "medicine_expiry"),
        _chart_copy(charts, "medicine_turnover_rate"),
    ]

    return DashboardModuleSchema(
        key="vet_pharmacy",
        title="Вет аптека",
        description="Контроль приходов/расходов лекарств, сроков годности и складских рисков.",
        kpis=[
            _metric_from(metrics, "arrivals", key="medicine_arrivals", label="Приход лекарств", unit="ед."),
            _metric_from(metrics, "consumptions", key="medicine_consumed", label="Расход лекарств", unit="ед."),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            _metric_from(metrics, "stock", key="current_stock", label="Текущий остаток", unit="ед."),
            _metric(key="expiring_batches", label="Партии скоро истекают", value=expiring_count, unit="шт"),
            _metric(key="expired_batches", label="Просрочено / заблокировано", value=expired_count, unit="шт"),
            _metric_from(metrics, "turnover_rate", key="turnover_rate", label="Turnover rate", unit="%"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("medicine_suppliers"),
                key="medicine_suppliers",
                title="Клиентская база вет аптеки",
                description="Контрагенты, которые участвуют в приходе и расходе лекарств.",
            ),
            DashboardTableSchema(
                key="medicine_client_registry",
                title="Активная клиентская база",
                description="Поставщики и получатели, реально участвовавшие в движении лекарств за период.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            _table_from_breakdown(
                breakdowns.get("medicine_batches"),
                key="medicine_expiry_batches",
                title="Партии со сроками годности",
                description="Партии с ближайшими сроками и остатком.",
            ),
            DashboardTableSchema(
                key="medicine_recent_batches",
                title="Последние партии прихода",
                description="Последние принятые партии со штрихкодом и сроком годности.",
                items=_table_items_from_rows(recent_batches_rows),
            ),
            DashboardTableSchema(
                key="medicine_latest_consumptions",
                title="Последние списания / выдачи",
                description="Последние расходные операции по лекарствам.",
                items=_table_items_from_rows(latest_consumptions_rows),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )


async def _build_slaughterhouse_dashboard_module(
    db: Database,
    start_date: date | None,
    end_date: date | None,
    department_ids: list[UUID] | None,
) -> DashboardModuleSchema:
    base = await _build_slaughterhouse_section(db, start_date, end_date, department_ids)
    metrics = _metric_map(base)
    charts = _chart_map(base)
    breakdowns = _breakdown_map(base)
    finance_analytics = await _build_module_finance_analytics(
        db,
        module_key="slaughter",
        module_prefix="slaughter",
        start_date=start_date,
        end_date=end_date,
        department_ids=department_ids,
    )

    semi_flow_rows = await db.fetch(
        f"""
        WITH produced AS (
            SELECT TO_CHAR(ssp.produced_on, 'YYYY-MM-DD') AS label, SUM(ssp.quantity) AS produced
            FROM slaughter_semi_products ssp
            INNER JOIN departments d ON d.id = ssp.department_id
            WHERE d.module_key = 'slaughter'
              AND {_date_condition('ssp.produced_on')}
              AND {_department_condition('ssp.department_id')}
            GROUP BY ssp.produced_on
        ),
        shipments AS (
            SELECT TO_CHAR(ss.shipped_on, 'YYYY-MM-DD') AS label, SUM(ss.quantity) AS shipped
            FROM slaughter_semi_product_shipments ss
            INNER JOIN departments d ON d.id = ss.department_id
            WHERE d.module_key = 'slaughter'
              AND {_date_condition('ss.shipped_on')}
              AND {_department_condition('ss.department_id')}
            GROUP BY ss.shipped_on
        )
        SELECT
            COALESCE(produced.label, shipments.label) AS label,
            COALESCE(produced.produced, 0) AS produced,
            COALESCE(shipments.shipped, 0) AS shipped
        FROM produced
        FULL OUTER JOIN shipments ON shipments.label = produced.label
        ORDER BY label
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_shipments_rows = await db.fetch(
        f"""
        SELECT
            ss.id::text AS key,
            CONCAT(TO_CHAR(ss.shipped_on, 'YYYY-MM-DD'), ' • ', {_client_label_sql('c')}) AS label,
            ss.quantity AS value,
            CONCAT('Выручка: ', ROUND(COALESCE(ss.unit_price, 0) * ss.quantity, 2)::text, ' UZS') AS caption
        FROM slaughter_semi_product_shipments ss
        INNER JOIN departments d ON d.id = ss.department_id
        INNER JOIN clients c ON c.id = ss.client_id
        WHERE d.module_key = 'slaughter'
          AND {_date_condition('ss.shipped_on')}
          AND {_department_condition('ss.department_id')}
        ORDER BY ss.shipped_on DESC, ss.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    client_registry_rows = await db.fetch(
        f"""
        WITH active_clients AS (
            SELECT
                sa.supplier_client_id AS client_id,
                COUNT(*) AS arrivals_count,
                SUM(sa.birds_count) AS birds_arrived,
                0::bigint AS shipments_count,
                0::numeric AS semi_shipped
            FROM slaughter_arrivals sa
            INNER JOIN departments d ON d.id = sa.department_id
            WHERE d.module_key = 'slaughter'
              AND sa.supplier_client_id IS NOT NULL
              AND {_date_condition('sa.arrived_on')}
              AND {_department_condition('sa.department_id')}
            GROUP BY sa.supplier_client_id

            UNION ALL

            SELECT
                ss.client_id AS client_id,
                0::bigint AS arrivals_count,
                0::numeric AS birds_arrived,
                COUNT(*) AS shipments_count,
                SUM(ss.quantity) AS semi_shipped
            FROM slaughter_semi_product_shipments ss
            INNER JOIN departments d ON d.id = ss.department_id
            WHERE d.module_key = 'slaughter'
              AND ss.client_id IS NOT NULL
              AND {_date_condition('ss.shipped_on')}
              AND {_department_condition('ss.department_id')}
            GROUP BY ss.client_id
        )
        SELECT
            c.id::text AS key,
            {_client_label_sql('c')} AS label,
            SUM(active_clients.arrivals_count + active_clients.shipments_count) AS value,
            'операций' AS unit,
            CONCAT(
                COALESCE(NULLIF(c.phone, ''), 'без телефона'),
                ' • роль: ',
                CASE
                    WHEN SUM(active_clients.birds_arrived) > 0 AND SUM(active_clients.semi_shipped) > 0
                    THEN 'поставщик и покупатель'
                    WHEN SUM(active_clients.birds_arrived) > 0
                    THEN 'поставщик птицы'
                    ELSE 'покупатель полуфабриката'
                END,
                ' • птица: ',
                ROUND(SUM(active_clients.birds_arrived), 3)::text,
                ' шт • полуфабрикат: ',
                ROUND(SUM(active_clients.semi_shipped), 3)::text,
                ' кг'
            ) AS caption
        FROM active_clients
        INNER JOIN clients c ON c.id = active_clients.client_id
        GROUP BY c.id, c.company_name, c.first_name, c.last_name, c.client_code, c.phone
        ORDER BY value DESC, label
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_arrivals_rows = await db.fetch(
        f"""
        SELECT
            sa.id::text AS key,
            CONCAT(
                TO_CHAR(sa.arrived_on, 'YYYY-MM-DD'),
                ' • ',
                COALESCE(NULLIF({_client_label_sql('c')}, 'Клиент'), 'внутренний поток')
            ) AS label,
            sa.birds_count AS value,
            CONCAT(
                'Средний вес: ',
                COALESCE(ROUND(sa.average_weight_kg, 3)::text, '—'),
                ' кг'
            ) AS caption
        FROM slaughter_arrivals sa
        INNER JOIN departments d ON d.id = sa.department_id
        LEFT JOIN clients c ON c.id = sa.supplier_client_id
        WHERE d.module_key = 'slaughter'
          AND {_date_condition('sa.arrived_on')}
          AND {_department_condition('sa.department_id')}
        ORDER BY sa.arrived_on DESC, sa.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )
    recent_processings_rows = await db.fetch(
        f"""
        SELECT
            sp.id::text AS key,
            CONCAT(
                TO_CHAR(sp.processed_on, 'YYYY-MM-DD'),
                ' • переработка'
            ) AS label,
            sp.birds_processed AS value,
            CONCAT(
                '1 сорт: ',
                sp.first_sort_count::text,
                ' • 2 сорт: ',
                sp.second_sort_count::text,
                ' • брак: ',
                sp.bad_count::text
            ) AS caption
        FROM slaughter_processings sp
        INNER JOIN departments d ON d.id = sp.department_id
        WHERE d.module_key = 'slaughter'
          AND {_date_condition('sp.processed_on')}
          AND {_department_condition('sp.department_id')}
        ORDER BY sp.processed_on DESC, sp.created_at DESC
        LIMIT 8
        """,
        start_date,
        end_date,
        department_ids,
    )

    process_rate = metrics.get("process_rate").value if metrics.get("process_rate") is not None else 0.0
    first_sort_share = metrics.get("first_sort_share").value if metrics.get("first_sort_share") is not None else 0.0
    alerts: list[DashboardAlertSchema] = []
    if process_rate < 80:
        alerts.append(
            DashboardAlertSchema(
                key="slaughter_process_rate_low",
                level="warning",
                title="Низкий process rate",
                message="Обработка отстаёт от входящего потока птицы.",
                value=process_rate,
                unit="%",
            )
        )
    if first_sort_share < 55:
        alerts.append(
            DashboardAlertSchema(
                key="slaughter_first_sort_share_low",
                level="warning",
                title="Низкая доля first sort",
                message="Доля первого сорта ниже операционного ориентира.",
                value=first_sort_share,
                unit="%",
            )
        )

    selected_charts = [
        _chart_copy(charts, "slaughter_flow"),
        _chart_copy(charts, "slaughter_quality"),
        _chart_copy(charts, "slaughter_semi_products"),
        _chart_copy(charts, "slaughter_process_rate"),
        DashboardChartSchema(
            key="slaughter_semi_flow",
            title="Выпуск / отгрузка полуфабрикатов",
            description="Сравнение выпуска и клиентской отгрузки полуфабрикатов.",
            type="line",
            unit="кг",
            series=_wide_series(
                semi_flow_rows,
                ("produced", "Выпуск", "produced"),
                ("shipped", "Отгрузка", "shipped"),
            ),
        ),
        _chart_copy(charts, "slaughter_revenue"),
    ]

    return DashboardModuleSchema(
        key="slaughterhouse",
        title="Убойня",
        description="Приход птицы, сортировка, разделка, полуфабрикат и клиентский поток убойного контура.",
        kpis=[
            _metric_from(metrics, "arrivals", key="birds_arrived", label="Птицы пришло", unit="шт"),
            _metric_from(metrics, "processed", key="birds_processed", label="Птицы обработано", unit="шт"),
            _metric_from(metrics, "first_sort_total", key="first_sort_total", label="Первый сорт", unit="шт"),
            _metric_from(metrics, "second_sort_total", key="second_sort_total", label="Второй сорт", unit="шт"),
            _metric_from(metrics, "bad_total", key="bad_total", label="Брак / плохой", unit="шт"),
            _metric_from(metrics, "process_rate", key="process_rate", label="Process rate", unit="%"),
            _metric_from(metrics, "first_sort_share", key="first_sort_share", label="Доля first sort", unit="%"),
            _metric_from(metrics, "semi_products", key="semi_product_output", label="Объём полуфабрикатов", unit="кг"),
            _metric_from(metrics, "sales_volume", key="shipment_volume", label="Отгружено полуфабриката", unit="кг"),
            _metric_from(metrics, "sales_revenue", key="shipment_revenue", label="Выручка от отгрузок", unit="UZS"),
            _metric_from(metrics, "client_base", key="client_base", label="Клиентская база", unit="клиентов"),
            *finance_analytics.metrics,
        ],
        charts=[chart for chart in [*selected_charts, *finance_analytics.charts] if chart is not None],
        tables=[
            _table_from_breakdown(
                breakdowns.get("slaughter_parts"),
                key="slaughter_top_products",
                title="Топ полуфабрикаты",
                description="Наиболее объёмные позиции по выпуску.",
            ),
            _table_from_breakdown(
                breakdowns.get("slaughter_clients"),
                key="slaughter_clients",
                title="Клиенты по полуфабрикату",
                description="Какие клиенты дают основной сбыт и выручку по полуфабрикату.",
            ),
            DashboardTableSchema(
                key="slaughter_client_registry",
                title="Активная клиентская база",
                description="Поставщики птицы и покупатели полуфабриката, участвовавшие в операциях за период.",
                items=_table_items_from_rows(client_registry_rows),
            ),
            DashboardTableSchema(
                key="slaughter_recent_arrivals",
                title="Последний приход птицы",
                description="Последние зафиксированные поступления птицы в убойный контур.",
                items=_table_items_from_rows(recent_arrivals_rows, default_unit="шт"),
            ),
            DashboardTableSchema(
                key="slaughter_recent_processings",
                title="Последняя разделка",
                description="Последние операции переработки с разрезом по сортам и браку.",
                items=_table_items_from_rows(recent_processings_rows, default_unit="шт"),
            ),
            DashboardTableSchema(
                key="slaughter_recent_shipments",
                title="Последние отгрузки клиентам",
                description="Последние клиентские отгрузки полуфабрикатов.",
                items=_table_items_from_rows(recent_shipments_rows, default_unit="кг"),
            ),
            *finance_analytics.tables,
        ],
        alerts=[*alerts, *finance_analytics.alerts],
    )


@router.get(
    "/analytics",
    response_model=DashboardAnalyticsResponseSchema,
    dependencies=[Depends(get_current_actor), Depends(require_access("dashboard.read"))],
    name="dashboard_analytics",
    operation_id="get_dashboard_analytics",
)
async def get_dashboard_analytics(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    department_id: UUID | None = Query(default=None),
    current_actor: CurrentActor = Depends(get_current_actor),
    db: Database = Depends(db_dependency),
) -> DashboardAnalyticsResponseSchema:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be before or equal to end_date")

    previous_start_date, previous_end_date = _resolve_previous_period(start_date, end_date)
    department_ids, scope = await _resolve_department_scope(
        db,
        department_id,
        organization_id=current_actor.organization_id,
        start_date=start_date,
        end_date=end_date,
    )
    currency_code = await _resolve_currency_code(db, current_actor.organization_id)
    modules = [
        await _build_egg_dashboard_module(db, start_date, end_date, department_ids),
        await _build_incubation_dashboard_module(db, start_date, end_date, department_ids),
        await _build_factory_dashboard_module(db, start_date, end_date, department_ids),
        await _build_feed_mill_dashboard_module(db, start_date, end_date, department_ids),
        await _build_vet_pharmacy_dashboard_module(db, start_date, end_date, department_ids),
        await _build_slaughterhouse_dashboard_module(db, start_date, end_date, department_ids),
    ]
    modules = [_apply_currency_code(module, currency_code) for module in modules]
    previous_modules_by_key: dict[str, DashboardModuleSchema] = {}
    if previous_start_date is not None and previous_end_date is not None:
        previous_department_ids, _ = await _resolve_department_scope(
            db,
            department_id,
            organization_id=current_actor.organization_id,
            start_date=previous_start_date,
            end_date=previous_end_date,
        )
        previous_modules = [
            await _build_egg_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
            await _build_incubation_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
            await _build_factory_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
            await _build_feed_mill_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
            await _build_vet_pharmacy_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
            await _build_slaughterhouse_dashboard_module(
                db,
                previous_start_date,
                previous_end_date,
                previous_department_ids,
            ),
        ]
        previous_modules = [_apply_currency_code(module, currency_code) for module in previous_modules]
        previous_modules_by_key = {module.key: module for module in previous_modules}

    modules = [
        _enrich_module_metrics(module, previous_modules_by_key.get(module.key))
        for module in modules
    ]

    return DashboardAnalyticsResponseSchema(
        generatedAt=datetime.now(timezone.utc),
        currency=currency_code,
        scope=scope,
        department_dashboard=DashboardDepartmentDashboardSchema(modules=modules),
        executive_dashboard=None,
    )


__all__ = ["router"]
