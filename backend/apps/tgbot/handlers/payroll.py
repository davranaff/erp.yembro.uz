"""
Payroll handlers для Telegram-бота:
    /zp [search] — баланс ЗП всех сотрудников (для HR), опц. фильтр по имени
    /myzp        — баланс сотрудника, привязанного к этому Telegram-аккаунту

Не запускают выплаты. Read-only — для оперативного просмотра.
"""
from __future__ import annotations

import html
import logging
from datetime import date
from decimal import Decimal

from ..bot import send_message
from ..dispatcher import HandlerCtx, command


logger = logging.getLogger(__name__)


def _fmt_uzs(value) -> str:
    if value is None or value == "":
        return "—"
    n = Decimal(str(value))
    return f"{n:,.0f}".replace(",", " ")


def _fmt_balance_line(name: str, accrued: Decimal, paid: Decimal, balance: Decimal) -> str:
    sign = "+" if balance > 0 else ("−" if balance < 0 else "·")
    return (
        f"<b>{html.escape(name)}</b>\n"
        f"  Начислено: <code>{_fmt_uzs(accrued)}</code>\n"
        f"  Выплачено: <code>{_fmt_uzs(paid)}</code>\n"
        f"  Баланс:    <code>{sign} {_fmt_uzs(abs(balance))}</code>"
    )


@command(
    "/zp",
    help="Балансы ЗП всех сотрудников (фильтр по ФИО)",
    module="hr", category="reports",
)
def handle_zp_cmd(ctx: HandlerCtx) -> None:
    """Список балансов всех активных сотрудников. /zp иван — фильтр по подстроке."""
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.services.balance import compute_balance

    org = ctx.org()
    if org is None:
        send_message(ctx.chat_id, "Активная организация не выбрана.")
        return

    search = " ".join(ctx.args).strip().lower() if ctx.args else ""
    qs = OrganizationMembership.objects.filter(
        organization=org, is_active=True,
    ).select_related("user")
    if search:
        qs = qs.filter(user__full_name__icontains=search)
    qs = qs[:20]

    if not qs.exists():
        send_message(ctx.chat_id, "Нет активных сотрудников.")
        return

    today = date.today()
    lines = ["💵 <b>Балансы ЗП</b>\n"]
    total_debt = Decimal("0")
    rows = []
    for m in qs:
        bal = compute_balance(m, today)
        rows.append((m, bal))
        if bal.balance_uzs > 0:
            total_debt += bal.balance_uzs
    rows.sort(key=lambda x: x[1].balance_uzs, reverse=True)

    for m, bal in rows:
        lines.append(_fmt_balance_line(
            m.user.full_name if m.user_id else "—",
            bal.accrued_total, bal.paid_total, bal.balance_uzs,
        ))
    lines.append(f"\n─\nДолг компании: <b>{_fmt_uzs(total_debt)}</b> сум")
    send_message(ctx.chat_id, "\n\n".join(lines))


@command(
    "/myzp",
    help="Мой баланс зарплаты",
    audience="any", category="reports",
)
def handle_myzp_cmd(ctx: HandlerCtx) -> None:
    """
    Если link принадлежит TgLink с user_id — показываем балансы юзера во всех
    его активных организациях. Counterparty-link не имеет смысла.
    """
    from apps.organizations.models import OrganizationMembership
    from apps.payroll.services.balance import compute_balance

    user_id = getattr(ctx.link, "user_id", None) if ctx.link else None
    if user_id is None:
        send_message(ctx.chat_id, "Команда доступна только привязанным сотрудникам.")
        return

    memberships = (
        OrganizationMembership.objects.filter(user_id=user_id, is_active=True)
        .select_related("organization", "user")
    )
    if not memberships.exists():
        send_message(ctx.chat_id, "У вас нет активных мест работы.")
        return

    today = date.today()
    blocks = []
    for m in memberships:
        bal = compute_balance(m, today)
        blocks.append(
            f"🏢 <b>{html.escape(m.organization.code)}</b>\n"
            f"  Должность: {html.escape(m.position_title or '—')}\n"
            f"  Начислено: <code>{_fmt_uzs(bal.accrued_total)}</code>\n"
            f"  Выплачено: <code>{_fmt_uzs(bal.paid_total)}</code>\n"
            f"  <b>К выплате: {_fmt_uzs(bal.balance_uzs)} сум</b>"
        )
    send_message(ctx.chat_id, "💵 <b>Ваша зарплата</b>\n\n" + "\n\n".join(blocks))
