"""
Owner daily digest — вечерняя сводка за сегодня.

Структура сообщения:
    📅 Сводка · ДД.ММ.ГГГГ · <Орг>

    💵 ПОСТУПЛЕНИЯ СЕГОДНЯ
       по каждой кассе: сколько реально пришло
       итого

    💸 РАСХОДЫ СЕГОДНЯ
       итого расход

    💰 ОСТАТКИ КАСС
       по каждой кассе текущий баланс (всё время)
       итого

    🔴 ДЕБИТОРКА (все долги клиентов)

Отправляется в 20:00 Asia/Tashkent через owner_digest_task всем
admin-линкам с digest_enabled=True.

Можно вызывать руками через команду /digest для preview.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal


def _fmt(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


@dataclass
class CashChannelRow:
    label: str
    income_today: Decimal = Decimal("0")
    expense_today: Decimal = Decimal("0")
    balance: Decimal = Decimal("0")


@dataclass
class DigestData:
    on_date: date
    channels: list[CashChannelRow] = field(default_factory=list)
    total_income: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    total_balance: Decimal = Decimal("0")
    total_debt: Decimal = Decimal("0")


def build_digest(organization, *, on_date: date | None = None) -> DigestData:
    """Собрать DigestData за день on_date (default = сегодня)."""
    from django.db.models import Sum

    from apps.payments.models import Payment
    from apps.sales.models import SaleOrder

    on_date = on_date or date.today()

    channels: list[CashChannelRow] = []
    total_income = Decimal("0")
    total_expense = Decimal("0")
    total_balance = Decimal("0")

    for ch_value, ch_label in Payment.Channel.choices:
        base_qs = Payment.objects.filter(
            organization=organization,
            status=Payment.Status.POSTED,
            channel=ch_value,
        )

        income_today = (
            base_qs.filter(
                direction=Payment.Direction.IN,
                date=on_date,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )

        expense_today = (
            base_qs.filter(
                direction=Payment.Direction.OUT,
                date=on_date,
            ).aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )

        balance_in = (
            base_qs.filter(direction=Payment.Direction.IN)
            .aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )
        balance_out = (
            base_qs.filter(direction=Payment.Direction.OUT)
            .aggregate(s=Sum("amount_uzs"))["s"]
            or Decimal("0")
        )
        balance = balance_in - balance_out

        # Пропускаем каналы с нулевой активностью вообще
        if income_today == 0 and expense_today == 0 and balance == 0:
            continue

        channels.append(CashChannelRow(
            label=ch_label,
            income_today=income_today,
            expense_today=expense_today,
            balance=balance,
        ))
        total_income += income_today
        total_expense += expense_today
        total_balance += balance

    # Дебиторка: сумма всех непогашенных долгов клиентов
    debt_agg = SaleOrder.objects.filter(
        organization=organization,
        status=SaleOrder.Status.CONFIRMED,
        payment_status__in=[
            SaleOrder.PaymentStatus.UNPAID,
            SaleOrder.PaymentStatus.PARTIAL,
        ],
    ).aggregate(
        amt=Sum("amount_uzs"),
        paid=Sum("paid_amount_uzs"),
    )
    total_debt = (debt_agg["amt"] or Decimal("0")) - (debt_agg["paid"] or Decimal("0"))
    if total_debt < 0:
        total_debt = Decimal("0")

    return DigestData(
        on_date=on_date,
        channels=channels,
        total_income=total_income,
        total_expense=total_expense,
        total_balance=total_balance,
        total_debt=total_debt,
    )


def format_digest(data: DigestData, organization_name: str = "") -> str:
    """HTML-сообщение для Telegram. Читабельный формат с разделами."""
    org_line = f" · {organization_name}" if organization_name else ""
    date_str = data.on_date.strftime("%d.%m.%Y")

    lines: list[str] = [
        f"📅 <b>Сводка · {date_str}</b>{org_line}",
    ]

    # ── Поступления сегодня ──────────────────────────────────────
    lines.append("")
    lines.append("💵 <b>ПОСТУПЛЕНИЯ СЕГОДНЯ</b>")
    has_income = any(r.income_today > 0 for r in data.channels)
    if has_income:
        lines.append("<pre>")
        for r in data.channels:
            if r.income_today > 0:
                lines.append(f"{r.label:<14} {_fmt(r.income_today):>16} сум")
        if len([r for r in data.channels if r.income_today > 0]) > 1:
            lines.append("─" * 32)
            lines.append(f"{'Итого':<14} {_fmt(data.total_income):>16} сум")
        lines.append("</pre>")
    else:
        lines.append("<i>Поступлений не было</i>")

    # ── Расходы сегодня ─────────────────────────────────────────
    lines.append("")
    lines.append("💸 <b>РАСХОДЫ СЕГОДНЯ</b>")
    if data.total_expense > 0:
        lines.append("<pre>")
        for r in data.channels:
            if r.expense_today > 0:
                lines.append(f"{r.label:<14} {_fmt(r.expense_today):>16} сум")
        if len([r for r in data.channels if r.expense_today > 0]) > 1:
            lines.append("─" * 32)
            lines.append(f"{'Итого':<14} {_fmt(data.total_expense):>16} сум")
        lines.append("</pre>")
    else:
        lines.append("<i>Расходов не было</i>")

    # ── Остатки касс ────────────────────────────────────────────
    lines.append("")
    lines.append("💰 <b>ОСТАТКИ КАСС</b>")
    if data.channels:
        lines.append("<pre>")
        for r in data.channels:
            sign = "" if r.balance >= 0 else "−"
            lines.append(f"{r.label:<14} {sign}{_fmt(abs(r.balance)):>16} сум")
        if len(data.channels) > 1:
            lines.append("─" * 32)
            sign = "" if data.total_balance >= 0 else "−"
            lines.append(f"{'Итого':<14} {sign}{_fmt(abs(data.total_balance)):>16} сум")
        lines.append("</pre>")
    else:
        lines.append("<i>Нет данных</i>")

    # ── Дебиторка ───────────────────────────────────────────────
    lines.append("")
    lines.append("🔴 <b>ДЕБИТОРКА (все долги)</b>")
    debt_sign = "" if data.total_debt == 0 else ""
    lines.append("<pre>")
    lines.append(f"{'Итого долгов':<14} {_fmt(data.total_debt):>16} сум")
    lines.append("</pre>")

    lines.append("")
    lines.append("<i>Нажмите кнопку ниже чтобы открыть раздел:</i>")
    return "\n".join(lines)


def digest_keyboard() -> dict:
    """Inline-кнопки под дайджестом для быстрого перехода в разделы."""
    from apps.tgbot.keyboards import kb
    return kb([
        ("💵 Касса/банк",  "fin:cash"),
        ("👥 Должники",    "fin:debt"),
        ("📦 Склад",       "fin:stock"),
        ("🏠 Меню",        "home"),
    ], cols=2)
