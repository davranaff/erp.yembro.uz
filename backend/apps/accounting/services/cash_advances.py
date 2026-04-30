"""
Lifecycle подотчётных (CashAdvance).

  ISSUED  — деньги выданы, ждём отчёт от сотрудника
       ↓ report_advance(spent, returned)
  REPORTED — отчитался, но проводка ещё не сделана
       ↓ close_advance()
  CLOSED  — создана JE на расходную статью, остаток вернулся в кассу

Причина двух шагов: иногда сотрудник присылает чеки кусками, и хочется
зафиксировать «отчитался» раньше чем сделать финальную проводку
(допиливают expense_article, проверяют чеки и т.п.).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone


class CashAdvanceError(ValidationError):
    """Бизнес-ошибка lifecycle подотчёта."""


def _q_money(v: Decimal) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"))


@transaction.atomic
def report_advance(
    advance,
    *,
    spent_amount: Decimal,
    user,
) -> "CashAdvance":  # noqa: F821
    """ISSUED → REPORTED.

    Сотрудник принёс чеки. Заполняем spent + returned, статус → REPORTED.
    На этом этапе **не делаем проводку** — закрытие отдельным шагом.
    """
    from ..models import CashAdvance

    if advance.status != CashAdvance.Status.ISSUED:
        raise CashAdvanceError(
            {"status": f"Отчитаться можно только из ISSUED, текущий: {advance.status}."},
        )

    spent = _q_money(spent_amount)
    if spent < 0:
        raise CashAdvanceError({"spent_amount_uzs": "Не может быть отрицательным."})
    if spent > advance.amount_uzs:
        raise CashAdvanceError(
            {"spent_amount_uzs": (
                f"Потрачено {spent} больше чем выдано {advance.amount_uzs}."
            )},
        )
    returned = _q_money(advance.amount_uzs - spent)

    advance.spent_amount_uzs = spent
    advance.returned_amount_uzs = returned
    advance.status = CashAdvance.Status.REPORTED
    advance.save(update_fields=[
        "spent_amount_uzs", "returned_amount_uzs", "status", "updated_at",
    ])
    return advance


@transaction.atomic
def close_advance(advance, *, user, expense_article=None) -> "CashAdvance":  # noqa: F821
    """REPORTED → CLOSED.

    Создаёт JE: Дт расходная статья (через `expense_article.gl_subaccount`)
    Кт 71.01 (расчёты с подотчётными лицами) на `spent_amount_uzs`.
    Возврат остатка (`returned_amount_uzs`) — отдельным Payment IN
    (создаётся вручную через UI кассы; здесь не автоматизируем чтобы не
    ломать кассу-первичку).
    """
    from apps.common.services.numbering import next_doc_number

    from ..models import CashAdvance, GLSubaccount, JournalEntry

    if advance.status != CashAdvance.Status.REPORTED:
        raise CashAdvanceError(
            {"status": f"Закрыть можно только из REPORTED, текущий: {advance.status}."},
        )
    if advance.spent_amount_uzs <= 0:
        # Если ничего не потратили — закрываем без JE, просто меняем статус.
        # (например выдали 1М, всё вернули обратно)
        advance.status = CashAdvance.Status.CLOSED
        advance.closed_date = timezone.now().date()
        advance.save(update_fields=["status", "closed_date", "updated_at"])
        return advance

    # Резолвим expense_article: или передан, или с самого advance
    article = expense_article or advance.expense_article
    if article is None:
        raise CashAdvanceError(
            {"expense_article": (
                "Для закрытия с проводкой нужна расходная статья "
                "(передайте expense_article или укажите её в подотчёте)."
            )},
        )

    debit_sub = article.gl_subaccount
    if debit_sub is None:
        raise CashAdvanceError(
            {"expense_article": (
                f"У статьи «{article.code}» нет привязки к субсчёту GL — "
                "доделайте справочник."
            )},
        )

    # 71.01 — расчёты с подотчётными лицами
    credit_sub = (
        GLSubaccount.objects.filter(
            account__organization=advance.organization,
            code="71.01",
        ).first()
    )
    if credit_sub is None:
        raise CashAdvanceError(
            {"detail": (
                "В плане счетов нет субсчёта 71.01 «Расчёты с подотчётными лицами». "
                "Создайте его в Settings → План счетов."
            )},
        )

    je = JournalEntry.objects.create(
        organization=advance.organization,
        doc_number=next_doc_number(
            JournalEntry, organization=advance.organization, prefix="ПР",
        ),
        entry_date=timezone.now().date(),
        description=(
            f"Закрытие подотчёта {advance.doc_number} · "
            f"{advance.recipient} · {advance.purpose[:80]}"
        ),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=advance.spent_amount_uzs,
        expense_article=article,
        created_by=user if (user and user.is_authenticated) else None,
    )

    advance.status = CashAdvance.Status.CLOSED
    advance.closed_date = timezone.now().date()
    advance.closing_journal_entry = je
    if expense_article and not advance.expense_article_id:
        advance.expense_article = expense_article
    advance.save(update_fields=[
        "status", "closed_date", "closing_journal_entry", "expense_article", "updated_at",
    ])
    return advance


@transaction.atomic
def cancel_advance(advance, *, user, reason: str = "") -> "CashAdvance":  # noqa: F821
    """ISSUED → CANCELLED.

    Используется когда деньги выдали по ошибке. Закрытые подотчёты
    отменять нельзя — там уже сделана проводка.
    """
    from ..models import CashAdvance

    if advance.status not in (CashAdvance.Status.ISSUED, CashAdvance.Status.REPORTED):
        raise CashAdvanceError(
            {"status": f"Отменить можно только из ISSUED/REPORTED, текущий: {advance.status}."},
        )

    advance.status = CashAdvance.Status.CANCELLED
    if reason:
        advance.notes = (advance.notes or "") + f"\n[Отмена] {reason}".strip()
    advance.save(update_fields=["status", "notes", "updated_at"])
    return advance
