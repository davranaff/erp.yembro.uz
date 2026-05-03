"""
Legacy команды: /report /balance /stock /cashflow /production.

Сохранены ради back-compat с пользователями, которые помнят их наизусть.
Семантически эквивалентны новым inline-меню в `finance.py` / `production.py`,
но не показываем их в setMyCommands (`private=True`) чтобы автокомплит был
чистым — подсказываем `/menu` вместо.
"""
from __future__ import annotations

import logging

from ..bot import send_message
from ..dispatcher import HandlerCtx, command
from ..notifications import fmt_cashflow, fmt_production, fmt_report, fmt_stock

logger = logging.getLogger(__name__)


@command("/report", help="Финансовый отчёт за месяц", module="reports", private=True)
def _report(ctx: HandlerCtx) -> None:
    from apps.dashboard.services import kpi_summary
    try:
        kpis = kpi_summary(ctx.org())
        send_message(ctx.chat_id, fmt_report(kpis))
    except Exception:  # noqa: BLE001
        logger.exception("legacy /report failed")
        send_message(ctx.chat_id, "⚠️ Не удалось получить отчёт.")


@command("/balance", help="Остатки кассы и банка", module="reports", private=True)
@command("/stock",   help="Остатки кассы и банка (alias)", module="reports", private=True)
def _balance(ctx: HandlerCtx) -> None:
    from apps.dashboard.services import cash_balances
    try:
        cash = cash_balances(ctx.org())
        send_message(ctx.chat_id, fmt_stock(cash))
    except Exception:  # noqa: BLE001
        logger.exception("legacy /balance failed")
        send_message(ctx.chat_id, "⚠️ Не удалось получить остатки.")


@command("/cashflow", help="Кэш-флоу за 30 дней", module="reports", private=True)
def _cashflow(ctx: HandlerCtx) -> None:
    from apps.dashboard.services import cashflow_chart
    try:
        points = cashflow_chart(ctx.org(), days=30)
        send_message(ctx.chat_id, fmt_cashflow(points, 30))
    except Exception:  # noqa: BLE001
        logger.exception("legacy /cashflow failed")
        send_message(ctx.chat_id, "⚠️ Не удалось получить кэш-флоу.")


@command("/production", help="Поголовье и партии (legacy)", module="feedlot", private=True)
def _production(ctx: HandlerCtx) -> None:
    from apps.dashboard.services import production_summary
    try:
        prod = production_summary(ctx.org())
        send_message(ctx.chat_id, fmt_production(prod))
    except Exception:  # noqa: BLE001
        logger.exception("legacy /production failed")
        send_message(ctx.chat_id, "⚠️ Не удалось получить данные производства.")
