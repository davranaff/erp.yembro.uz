"""
Атомарное создание выплаты ЗП: Payment + PayrollPayout.

Сценарий:
    1. Резолв ExpenseArticle(code='SALARY') и его default_subaccount (70.01).
    2. Создание Payment(kind=salary, direction=OUT, contra_subaccount=70.01).
    3. post_payment(...) → POSTED + JE.
    4. PayrollPayout(payment=...).
    5. audit_log.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounting.models import ExpenseArticle
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.common.services.numbering import next_doc_number
from apps.payments.models import Payment
from apps.payments.services.post import post_payment

from ..models import PayrollPayout


@transaction.atomic
def create_payout(
    *,
    employee,
    type: str,
    amount_uzs: Decimal,
    period_from: date,
    period_to: date,
    cash_subaccount,
    on_date: date | None = None,
    channel: str = Payment.Channel.CASH,
    notes: str = "",
    user=None,
    currency=None,
    exchange_rate: Decimal | None = None,
    amount_foreign: Decimal | None = None,
) -> PayrollPayout:
    """
    Создать выплату ЗП сотруднику.

    Args:
        employee: OrganizationMembership.
        type: PayrollPayout.Type значение.
        amount_uzs: сумма к выплате в UZS (всегда обязательна).
        period_from, period_to: за какой период.
        cash_subaccount: GLSubaccount кассы (50.X / 51.X).
        on_date: дата платежа (default today).
        channel: Payment.Channel (CASH/TRANSFER/CLICK/OTHER).
        notes: произвольная заметка.
        user: User-инициатор.

    FX (опционально, если выплата в валюте отличной от UZS):
        currency: Currency instance (например USD).
        exchange_rate: курс на дату выплаты (UZS за единицу currency).
        amount_foreign: сумма в иностранной валюте.
        Все три параметра должны быть заданы вместе или ни один.
        Связь: amount_uzs ≈ amount_foreign × exchange_rate (validate в Payment.clean).
    """
    org = employee.organization
    if amount_uzs is None or amount_uzs <= 0:
        raise ValidationError({"amount_uzs": "Сумма должна быть больше нуля."})
    if period_to < period_from:
        raise ValidationError({"period_to": "period_to раньше period_from."})

    fx_fields_set = sum(
        1 for v in (currency, exchange_rate, amount_foreign) if v is not None
    )
    if fx_fields_set not in (0, 3):
        raise ValidationError({
            "currency": (
                "Для валютной выплаты задайте currency + exchange_rate + amount_foreign "
                "одновременно."
            ),
        })
    is_fx = fx_fields_set == 3

    pay_date = on_date or date.today()

    salary_article = (
        ExpenseArticle.objects.filter(organization=org, code="SALARY", is_active=True)
        .select_related("default_subaccount__account")
        .first()
    )
    if salary_article is None:
        raise ValidationError(
            {"expense_article": "Не настроена статья SALARY для организации."}
        )
    if salary_article.default_subaccount_id is None:
        raise ValidationError(
            {"expense_article": "У статьи SALARY не задан субсчёт (70.01)."}
        )

    employee_label = (
        getattr(getattr(employee, "user", None), "full_name", "") or str(employee)
    )
    payment = Payment(
        organization=org,
        doc_number=next_doc_number(
            Payment, organization=org, prefix="ПЛ", on_date=pay_date,
        ),
        date=pay_date,
        direction=Payment.Direction.OUT,
        channel=channel,
        kind=Payment.Kind.SALARY,
        status=Payment.Status.DRAFT,
        amount_uzs=amount_uzs,
        currency=currency if is_fx else None,
        exchange_rate=exchange_rate if is_fx else None,
        amount_foreign=amount_foreign if is_fx else None,
        cash_subaccount=cash_subaccount,
        contra_subaccount=salary_article.default_subaccount,
        expense_article=salary_article,
        notes=notes or f"ЗП {employee_label} · {type}",
        created_by=user,
    )
    payment.full_clean()
    payment.save()
    post_payment(payment, user=user)
    payment.refresh_from_db()

    payout = PayrollPayout.objects.create(
        organization=org,
        employee=employee,
        type=type,
        period_from=period_from,
        period_to=period_to,
        payment=payment,
        amount_uzs=amount_uzs,
        notes=notes,
        created_by=user,
    )
    audit_log(
        organization=org,
        actor=user,
        action=AuditLog.Action.CREATE,
        entity=payout,
        action_verb=f"payout {type} {amount_uzs} to {employee_label}"[:64],
    )
    _apply_auto_taxes(payout)
    _notify_employee_payout(payout)
    return payout


def _apply_auto_taxes(payout: PayrollPayout) -> None:
    """Если в настройках org включено auto_apply_on_payout — применяет налоги."""
    try:
        from .taxes import apply_taxes_for_payout
        apply_taxes_for_payout(payout)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("payroll: failed to apply auto taxes")


def _notify_employee_payout(payout: PayrollPayout) -> None:
    """
    Отправляет Telegram-уведомление сотруднику, если у него привязан TgLink.
    Проглатывает любые ошибки (notifier не должен ронять create_payout).
    """
    try:
        from apps.tgbot.bot import send_message
        from apps.tgbot.models import TgLink
    except Exception:
        return
    try:
        link = TgLink.objects.filter(
            user_id=payout.employee.user_id,
            organization=payout.organization,
        ).first()
        if link is None:
            return
        amount = f"{payout.amount_uzs:,.0f}".replace(",", " ")
        text = (
            f"💵 <b>Выплата</b>\n\n"
            f"Тип: {payout.get_type_display()}\n"
            f"Период: {payout.period_from} — {payout.period_to}\n"
            f"Сумма: <code>{amount}</code> сум\n"
            f"Документ: {payout.payment.doc_number if payout.payment_id else '—'}"
        )
        send_message(link.chat_id, text)
    except Exception:
        import logging
        logging.getLogger(__name__).exception("payroll: failed to notify employee")
