"""
Тесты бухгалтерских отчётов: ОСВ, GL ledger, P&L.

Проверки:
  - opening + debit − credit = closing (для активов)
  - revenue − expense = profit
  - GL ledger running_balance корректен
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.accounting.models import GLAccount, GLSubaccount, JournalEntry
from apps.accounting.services.reports import (
    compute_gl_ledger,
    compute_pl_report,
    compute_trial_balance,
)
from apps.modules.models import Module
from apps.organizations.models import Organization
from apps.users.models import User


pytestmark = pytest.mark.django_db


@pytest.fixture
def org():
    return Organization.objects.get(code="DEFAULT")


@pytest.fixture
def m_ledger():
    return Module.objects.get(code="ledger")


@pytest.fixture
def user():
    return User.objects.create(email="rep@y.local", full_name="Reporter")


@pytest.fixture
def sub_10_05(org):
    """10.05 — корм на складе (актив)."""
    return GLSubaccount.objects.filter(
        account__organization=org, code="10.05",
    ).first()


@pytest.fixture
def sub_60_01(org):
    """60.01 — расчёты с поставщиками (пассив)."""
    return GLSubaccount.objects.filter(
        account__organization=org, code="60.01",
    ).first()


@pytest.fixture
def sub_90_01(org):
    """90.01 — выручка (доход)."""
    return GLSubaccount.objects.filter(
        account__organization=org, code="90.01",
    ).first()


@pytest.fixture
def sub_90_02(org):
    """90.02 — себестоимость (расход)."""
    return GLSubaccount.objects.filter(
        account__organization=org, code="90.02",
    ).first()


# ─── Trial Balance ───────────────────────────────────────────────


def test_trial_balance_simple_purchase(org, m_ledger, sub_10_05, sub_60_01, user):
    """
    Сценарий: одна закупка → Дт 10.05 / Кт 60.01 на 1 000 000.
    ОСВ за период должна показать:
      10.05 (актив): нач=0, дебет=1М, кредит=0, конец=+1М
      60.01 (пассив): нач=0, дебет=0, кредит=1М, конец=+1М (т.е. кредитовый остаток)
    """
    if not (sub_10_05 and sub_60_01):
        pytest.skip("Нужны субсчета 10.05 и 60.01 в seed")

    JournalEntry.objects.create(
        organization=org, module=m_ledger,
        doc_number="ПР-TB-001", entry_date=date(2026, 5, 1),
        description="Тест: закупка",
        debit_subaccount=sub_10_05, credit_subaccount=sub_60_01,
        amount_uzs=Decimal("1000000.00"),
        created_by=user,
    )

    rows = compute_trial_balance(
        org,
        date_from=date(2026, 5, 1),
        date_to=date(2026, 5, 31),
    )
    by_code = {r.subaccount_code: r for r in rows}

    assert "10.05" in by_code
    r = by_code["10.05"]
    assert r.opening_balance == Decimal("0.00")
    assert r.debit_turnover == Decimal("1000000.00")
    assert r.credit_turnover == Decimal("0.00")
    assert r.closing_balance == Decimal("1000000.00")

    assert "60.01" in by_code
    r = by_code["60.01"]
    assert r.opening_balance == Decimal("0.00")
    assert r.debit_turnover == Decimal("0.00")
    assert r.credit_turnover == Decimal("1000000.00")
    # Для пассива closing = − debit + credit = 0 + 1М = +1М (кредитовый остаток)
    assert r.closing_balance == Decimal("1000000.00")


def test_trial_balance_skips_zeros_by_default(org, m_ledger, sub_10_05, sub_60_01, user):
    """Если нет проводок и include_zeros=False — субсчёт не попадает в ответ."""
    rows = compute_trial_balance(
        org,
        date_from=date(2099, 1, 1),
        date_to=date(2099, 12, 31),
    )
    # Все субсчета должны иметь все нули за далёкий 2099 → пусто
    assert rows == []


# ─── GL Ledger ─────────────────────────────────────────────────


def test_gl_ledger_running_balance(org, m_ledger, sub_10_05, sub_60_01, user):
    """
    Две проводки: приход (+1М) и сторно (−1М). Running balance должен
    идти 0 → 1М → 0.
    """
    if not (sub_10_05 and sub_60_01):
        pytest.skip("Нужны субсчета 10.05 и 60.01")

    JournalEntry.objects.create(
        organization=org, module=m_ledger,
        doc_number="ПР-LD-001", entry_date=date(2026, 6, 1),
        description="Приход",
        debit_subaccount=sub_10_05, credit_subaccount=sub_60_01,
        amount_uzs=Decimal("1000000.00"),
        created_by=user,
    )
    JournalEntry.objects.create(
        organization=org, module=m_ledger,
        doc_number="ПР-LD-002", entry_date=date(2026, 6, 2),
        description="Сторно",
        debit_subaccount=sub_60_01, credit_subaccount=sub_10_05,
        amount_uzs=Decimal("1000000.00"),
        created_by=user,
    )

    result = compute_gl_ledger(
        org, sub_10_05,
        date_from=date(2026, 6, 1), date_to=date(2026, 6, 30),
    )
    assert result.opening_balance == Decimal("0.00")
    assert len(result.entries) == 2
    # Первая: дебет 1М → running = +1М
    assert result.entries[0].debit_amount == Decimal("1000000.00")
    assert result.entries[0].running_balance == Decimal("1000000.00")
    # Вторая: кредит 1М → running = 0
    assert result.entries[1].credit_amount == Decimal("1000000.00")
    assert result.entries[1].running_balance == Decimal("0.00")
    assert result.closing_balance == Decimal("0.00")


# ─── P&L ──────────────────────────────────────────────────────


def test_pl_report_revenue_minus_expense_equals_profit(
    org, m_ledger, sub_90_01, sub_90_02, sub_60_01, user,
):
    """
    Доход 100 (90.01 ↑), расход 30 (90.02 ↑) → прибыль 70.
    """
    if not (sub_90_01 and sub_90_02 and sub_60_01):
        pytest.skip("Нужны субсчета 90.01, 90.02, 60.01")

    # Выручка: Дт 62.01 / Кт 90.01 = 100 (имитируем через 60.01 для простоты)
    JournalEntry.objects.create(
        organization=org, module=m_ledger,
        doc_number="ПР-PL-001", entry_date=date(2026, 7, 5),
        description="Выручка",
        debit_subaccount=sub_60_01, credit_subaccount=sub_90_01,
        amount_uzs=Decimal("100.00"),
        created_by=user,
    )
    # Себестоимость: Дт 90.02 / Кт 60.01 = 30
    JournalEntry.objects.create(
        organization=org, module=m_ledger,
        doc_number="ПР-PL-002", entry_date=date(2026, 7, 5),
        description="Себестоимость",
        debit_subaccount=sub_90_02, credit_subaccount=sub_60_01,
        amount_uzs=Decimal("30.00"),
        created_by=user,
    )

    result = compute_pl_report(
        org,
        date_from=date(2026, 7, 1),
        date_to=date(2026, 7, 31),
    )
    # В seed 90.01 (Выручка) и 90.02 (Себестоимость) — оба на счёте 90 type='income'.
    # Свёрнуто: revenue = (90.01 credit − 90.01 debit) + (90.02 credit − 90.02 debit)
    #         = (100 − 0) + (0 − 30) = 70.
    # Expense (счета type='expense', напр. 20/26/91) — пусто.
    assert result.total_revenue == Decimal("70.00")
    assert result.total_expense == Decimal("0.00")
    assert result.profit == Decimal("70.00")
