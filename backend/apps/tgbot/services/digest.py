"""
Owner daily digest — компактная сводка за вчерашний день.

Структура сообщения:
    📅 Сводка за <дата>
    💸 Выручка: X (Δ vs позавчера)
    💰 Касса/банк: Y
    🟢/🔴 P&L дня: Z
    🚨 Алерты (если есть): низкая яйценоскость, высокий падёж, hatch rate
    📦 Активных партий: N

Отправляется в 08:00 Asia/Tashkent через `owner_digest_task` всем
admin-линкам с `digest_enabled=True`.

Можно вызывать руками через команду `/digest` для preview.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal


def _fmt_uzs(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


def _fmt_delta(value: Decimal) -> str:
    """+5M / −1.2M / =0 — короткая разница."""
    sign = "+" if value > 0 else ("−" if value < 0 else "=")
    abs_v = abs(value)
    return f"{sign}{_fmt_uzs(abs_v)}"


@dataclass
class DigestData:
    on_date: date
    revenue: Decimal = Decimal("0")
    revenue_delta: Decimal = Decimal("0")
    expense: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")
    cash_total: Decimal = Decimal("0")
    active_batches: int = 0
    alerts: list[str] = field(default_factory=list)


def build_digest(organization, *, on_date: date | None = None) -> DigestData:
    """Собрать DigestData за день `on_date` (default = вчера)."""
    from apps.accounting.services.reports import compute_pl_report
    from apps.batches.models import Batch
    from apps.dashboard.services import cash_balances

    on_date = on_date or (date.today() - timedelta(days=1))
    prev_date = on_date - timedelta(days=1)

    # P&L за on_date
    today_pl = compute_pl_report(
        organization, date_from=on_date, date_to=on_date,
    )
    yest_pl = compute_pl_report(
        organization, date_from=prev_date, date_to=prev_date,
    )

    cash = cash_balances(organization)
    cash_total = Decimal(str(cash.get("_total_uzs", "0")))

    active_batches = Batch.objects.filter(
        organization=organization,
        state__in=[
            Batch.State.ACTIVE,
            Batch.State.IN_TRANSIT,
            Batch.State.REVIEW,
        ],
    ).count()

    alerts = _collect_alert_lines(organization)

    return DigestData(
        on_date=on_date,
        revenue=today_pl.total_revenue,
        revenue_delta=today_pl.total_revenue - yest_pl.total_revenue,
        expense=today_pl.total_expense,
        profit=today_pl.profit,
        cash_total=cash_total,
        active_batches=active_batches,
        alerts=alerts,
    )


def _collect_alert_lines(organization) -> list[str]:
    """Собирает короткие строки активных алертов из feedlot/incubation/matочник
    KPI коллекторов. Топ-5 по важности (просто склеивает в порядке модулей)."""
    out: list[str] = []
    try:
        from apps.feedlot.services.kpi_alerts import collect_org_alerts as feedlot_alerts
        for a in feedlot_alerts(organization)[:3]:
            out.append(f"🚨 Откорм {a.batch_doc}: {a.kind} {a.value} (норма {a.threshold})")
    except Exception:  # noqa: BLE001
        pass
    try:
        from apps.matochnik.services.kpi_alerts import collect_org_alerts as mat_alerts
        for a in mat_alerts(organization)[:3]:
            out.append(f"🚨 Маточник {a.herd_doc}: {a.kind} {a.value} (порог {a.threshold})")
    except Exception:  # noqa: BLE001
        pass
    try:
        from apps.incubation.services.kpi_alerts import collect_org_alerts as inc_alerts
        for a in inc_alerts(organization)[:3]:
            out.append(
                f"🚨 Инкубация {a.run_doc}: hatch rate {a.hatch_rate_pct}% "
                f"(норма ≥ {a.threshold_pct}%)"
            )
    except Exception:  # noqa: BLE001
        pass
    return out[:5]


def format_digest(data: DigestData, organization_name: str = "") -> str:
    """HTML-сообщение для send_message. Моноширинная таблица."""
    org_line = f" · {organization_name}" if organization_name else ""

    # Основная финансовая таблица.
    pl_rows = [
        f"Выручка    {_fmt_uzs(data.revenue):>14} сум",
        f"           {_fmt_delta(data.revenue_delta):>14}  к пред. дню",
        f"Расходы    {_fmt_uzs(data.expense):>14} сум",
        "─" * 30,
        f"Прибыль    {_fmt_delta(data.profit):>14} сум",
    ]

    # Производственная таблица.
    op_rows = [
        f"Касса/банк       {_fmt_uzs(data.cash_total):>14} сум",
        f"Активных партий  {str(data.active_batches):>14}",
    ]

    lines = [
        f"📅 <b>Сводка за {data.on_date.isoformat()}</b>{org_line}",
        "",
        "<pre>" + "\n".join(pl_rows) + "</pre>",
        "<pre>" + "\n".join(op_rows) + "</pre>",
    ]

    if data.alerts:
        lines.append("<b>Активные алерты:</b>")
        for a in data.alerts:
            lines.append(f"  {a}")
        lines.append("")

    lines.append("<i>/menu — открыть полное меню</i>")
    return "\n".join(lines)
