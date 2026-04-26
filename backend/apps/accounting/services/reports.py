"""
Бухгалтерские отчёты: ОСВ (trial balance), GL ledger, P&L.

Все три функции — чистые select'ы без побочных эффектов. Возвращают
обычные dict'ы (не Decimal) — серилизация через DRF Response сделает str().
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from decimal import Decimal
from typing import Iterable, Optional

from django.db.models import Q, Sum

from ..models import GLAccount, GLSubaccount, JournalEntry


# ─── Helpers ─────────────────────────────────────────────────────────


def _opening_balance(
    subaccount: GLSubaccount, organization, before_date: date_cls
) -> Decimal:
    """
    Остаток на субсчёте до `before_date` (исключительно).

    Для активных/расходных счетов: + дебет, − кредит.
    Для пассивных/доходных/капитала: − дебет, + кредит.
    SERVICE — традиционно нейтральные, считаем как пассивные.
    """
    debit_total = (
        JournalEntry.objects
        .filter(
            organization=organization,
            debit_subaccount=subaccount,
            entry_date__lt=before_date,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    credit_total = (
        JournalEntry.objects
        .filter(
            organization=organization,
            credit_subaccount=subaccount,
            entry_date__lt=before_date,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    account_type = subaccount.account.type
    if account_type in (GLAccount.Type.ASSET, GLAccount.Type.EXPENSE):
        return debit_total - credit_total
    # liability / equity / income / service
    return credit_total - debit_total


def _period_turnover(
    subaccount: GLSubaccount, organization, date_from: date_cls, date_to: date_cls
) -> tuple[Decimal, Decimal]:
    """Возвращает (debit_turnover, credit_turnover) за [date_from, date_to]."""
    debit = (
        JournalEntry.objects
        .filter(
            organization=organization,
            debit_subaccount=subaccount,
            entry_date__gte=date_from,
            entry_date__lte=date_to,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    credit = (
        JournalEntry.objects
        .filter(
            organization=organization,
            credit_subaccount=subaccount,
            entry_date__gte=date_from,
            entry_date__lte=date_to,
        )
        .aggregate(s=Sum("amount_uzs"))["s"] or Decimal("0")
    )
    return debit, credit


def _closing_balance(
    opening: Decimal,
    debit: Decimal,
    credit: Decimal,
    account_type: str,
) -> Decimal:
    """
    Конечный остаток = opening ± turnover.
    Для активных/расходных: opening + debit − credit.
    Для пассивных/доходных/капитала: opening − debit + credit.
    """
    if account_type in (GLAccount.Type.ASSET, GLAccount.Type.EXPENSE):
        return opening + debit - credit
    return opening - debit + credit


# ─── Trial Balance ────────────────────────────────────────────────────


@dataclass
class TrialBalanceRow:
    subaccount_id: str
    subaccount_code: str
    subaccount_name: str
    account_code: str
    account_name: str
    account_type: str
    module_code: Optional[str]
    opening_balance: Decimal
    debit_turnover: Decimal
    credit_turnover: Decimal
    closing_balance: Decimal


def compute_trial_balance(
    organization,
    *,
    date_from: date_cls,
    date_to: date_cls,
    module_code: Optional[str] = None,
    include_zeros: bool = False,
) -> list[TrialBalanceRow]:
    """
    Оборотная ведомость по всем субсчетам организации.

    Если `include_zeros=False` — отбрасываем строки где все 4 числа = 0.
    """
    subs = (
        GLSubaccount.objects
        .filter(account__organization=organization)
        .select_related("account", "module")
    )
    if module_code:
        subs = subs.filter(module__code=module_code)

    rows: list[TrialBalanceRow] = []
    for sub in subs:
        opening = _opening_balance(sub, organization, date_from)
        debit, credit = _period_turnover(sub, organization, date_from, date_to)
        closing = _closing_balance(opening, debit, credit, sub.account.type)

        if not include_zeros and not (opening or debit or credit or closing):
            continue

        rows.append(TrialBalanceRow(
            subaccount_id=str(sub.id),
            subaccount_code=sub.code,
            subaccount_name=sub.name,
            account_code=sub.account.code,
            account_name=sub.account.name,
            account_type=sub.account.type,
            module_code=sub.module.code if sub.module_id else None,
            opening_balance=opening,
            debit_turnover=debit,
            credit_turnover=credit,
            closing_balance=closing,
        ))

    rows.sort(key=lambda r: (r.account_code, r.subaccount_code))
    return rows


# ─── GL Ledger ────────────────────────────────────────────────────────


@dataclass
class GlLedgerEntry:
    entry_id: str
    doc_number: str
    entry_date: str
    description: str
    debit_amount: Optional[Decimal]
    credit_amount: Optional[Decimal]
    running_balance: Decimal
    counterparty_name: Optional[str]
    module_code: Optional[str]


@dataclass
class GlLedgerResult:
    subaccount_id: str
    subaccount_code: str
    subaccount_name: str
    account_code: str
    account_name: str
    account_type: str
    opening_balance: Decimal
    closing_balance: Decimal
    total_debit: Decimal
    total_credit: Decimal
    entries: list[GlLedgerEntry] = field(default_factory=list)


def compute_gl_ledger(
    organization,
    subaccount: GLSubaccount,
    *,
    date_from: date_cls,
    date_to: date_cls,
) -> GlLedgerResult:
    """Главная книга по конкретному субсчёту с накопительным остатком."""
    opening = _opening_balance(subaccount, organization, date_from)
    account_type = subaccount.account.type
    is_debit_normal = account_type in (
        GLAccount.Type.ASSET, GLAccount.Type.EXPENSE
    )

    qs = (
        JournalEntry.objects
        .filter(organization=organization)
        .filter(
            Q(debit_subaccount=subaccount) | Q(credit_subaccount=subaccount)
        )
        .filter(entry_date__gte=date_from, entry_date__lte=date_to)
        .select_related("counterparty", "module")
        .order_by("entry_date", "doc_number", "created_at")
    )

    running = opening
    total_debit = Decimal("0")
    total_credit = Decimal("0")
    entries: list[GlLedgerEntry] = []

    for je in qs:
        debit_amount = None
        credit_amount = None
        if je.debit_subaccount_id == subaccount.id:
            debit_amount = je.amount_uzs
            total_debit += debit_amount
            running = running + debit_amount if is_debit_normal else running - debit_amount
        if je.credit_subaccount_id == subaccount.id:
            credit_amount = je.amount_uzs
            total_credit += credit_amount
            running = running - credit_amount if is_debit_normal else running + credit_amount

        entries.append(GlLedgerEntry(
            entry_id=str(je.id),
            doc_number=je.doc_number,
            entry_date=je.entry_date.isoformat(),
            description=je.description or "",
            debit_amount=debit_amount,
            credit_amount=credit_amount,
            running_balance=running,
            counterparty_name=(
                je.counterparty.name if je.counterparty_id else None
            ),
            module_code=je.module.code if je.module_id else None,
        ))

    return GlLedgerResult(
        subaccount_id=str(subaccount.id),
        subaccount_code=subaccount.code,
        subaccount_name=subaccount.name,
        account_code=subaccount.account.code,
        account_name=subaccount.account.name,
        account_type=account_type,
        opening_balance=opening,
        closing_balance=running,
        total_debit=total_debit,
        total_credit=total_credit,
        entries=entries,
    )


# ─── P&L ──────────────────────────────────────────────────────────────


@dataclass
class PlRow:
    subaccount_id: str
    subaccount_code: str
    subaccount_name: str
    amount: Decimal
    by_module: dict  # {module_code: amount}


@dataclass
class PlResult:
    date_from: str
    date_to: str
    revenue: list[PlRow] = field(default_factory=list)
    expense: list[PlRow] = field(default_factory=list)
    total_revenue: Decimal = Decimal("0")
    total_expense: Decimal = Decimal("0")
    profit: Decimal = Decimal("0")


def _pl_section(
    organization,
    *,
    account_type: str,
    date_from: date_cls,
    date_to: date_cls,
) -> tuple[list[PlRow], Decimal]:
    """
    Доход (income): сумма по credit − debit за период (доходы — кредитовый счёт).
    Расход (expense): сумма по debit − credit за период.
    """
    is_debit_normal = account_type == GLAccount.Type.EXPENSE
    rows: list[PlRow] = []
    total = Decimal("0")

    subs = (
        GLSubaccount.objects
        .filter(account__organization=organization, account__type=account_type)
        .select_related("account")
    )
    for sub in subs:
        debit, credit = _period_turnover(sub, organization, date_from, date_to)
        if is_debit_normal:
            amount = debit - credit
        else:
            amount = credit - debit

        if amount == 0:
            continue

        # Разрез по модулям
        je_qs = JournalEntry.objects.filter(
            organization=organization,
            entry_date__gte=date_from, entry_date__lte=date_to,
        ).filter(
            Q(debit_subaccount=sub) | Q(credit_subaccount=sub)
        ).select_related("module")

        by_module: dict[str, Decimal] = {}
        for je in je_qs:
            sign = Decimal("1")
            if is_debit_normal:
                if je.debit_subaccount_id == sub.id:
                    sign = Decimal("1")
                elif je.credit_subaccount_id == sub.id:
                    sign = Decimal("-1")
            else:
                if je.credit_subaccount_id == sub.id:
                    sign = Decimal("1")
                elif je.debit_subaccount_id == sub.id:
                    sign = Decimal("-1")
            mod = je.module.code if je.module_id else "—"
            by_module[mod] = (by_module.get(mod, Decimal("0"))) + sign * je.amount_uzs

        rows.append(PlRow(
            subaccount_id=str(sub.id),
            subaccount_code=sub.code,
            subaccount_name=sub.name,
            amount=amount,
            by_module={k: v for k, v in by_module.items() if v != 0},
        ))
        total += amount

    rows.sort(key=lambda r: r.subaccount_code)
    return rows, total


def compute_pl_report(
    organization,
    *,
    date_from: date_cls,
    date_to: date_cls,
) -> PlResult:
    """Отчёт о прибыли и убытках за период."""
    revenue, total_revenue = _pl_section(
        organization, account_type=GLAccount.Type.INCOME,
        date_from=date_from, date_to=date_to,
    )
    expense, total_expense = _pl_section(
        organization, account_type=GLAccount.Type.EXPENSE,
        date_from=date_from, date_to=date_to,
    )
    return PlResult(
        date_from=date_from.isoformat(),
        date_to=date_to.isoformat(),
        revenue=revenue,
        expense=expense,
        total_revenue=total_revenue,
        total_expense=total_expense,
        profit=total_revenue - total_expense,
    )
