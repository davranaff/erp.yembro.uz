"""
Сервис `check_customer_credit` — guard на confirm_sale.

Проверяет два независимых лимита покупателя:
    1. `credit_limit_uzs` — суммарная дебиторка не должна превышать лимит
       (включая сумму НОВОЙ продажи, которую сейчас проводим).
    2. `max_overdue_days` — самый старый непогашенный счёт не должен быть
       просрочен дольше N дней.

Источник истины — `compute_aging_report(org, customer_id=...)`. Не дублируем
логику расчёта просрочки и outstanding — иначе разъедутся.

Возвращает `CreditCheckResult` с полями:
    ok                : bool
    reasons           : list[str] — что именно не прошло
    current_debt_uzs  : Decimal — общая дебиторка клиента сейчас
    oldest_overdue    : int — макс. просрочка
    limit_uzs         : Decimal | None
    max_overdue_days  : int | None
    new_sale_uzs      : Decimal — сумма проводимой продажи
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional

from .aging import compute_aging_report


@dataclass
class CreditCheckResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)
    current_debt_uzs: Decimal = Decimal("0")
    oldest_overdue: int = 0
    limit_uzs: Optional[Decimal] = None
    max_overdue_days: Optional[int] = None
    new_sale_uzs: Decimal = Decimal("0")

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reasons": self.reasons,
            "current_debt_uzs": str(self.current_debt_uzs),
            "oldest_overdue_days": self.oldest_overdue,
            "limit_uzs": str(self.limit_uzs) if self.limit_uzs is not None else None,
            "max_overdue_days": self.max_overdue_days,
            "new_sale_uzs": str(self.new_sale_uzs),
            "projected_debt_uzs": str(self.current_debt_uzs + self.new_sale_uzs),
        }


def check_customer_credit(
    *,
    organization,
    customer,
    new_sale_uzs: Decimal = Decimal("0"),
) -> CreditCheckResult:
    """Проверка кредитного лимита и максимальной просрочки клиента.

    Параметры:
        organization: org для которой считаем
        customer:     Counterparty (предполагается kind=buyer; для других
                      kind лимиты обычно не заданы и check вернёт ok)
        new_sale_uzs: сумма НОВОЙ продажи (которая в проекции).
                      Учитывается в credit_limit-проверке, но не в overdue
                      (новая продажа ещё не просрочена).
    """
    limit = customer.credit_limit_uzs
    max_od = customer.max_overdue_days

    # Если ни один лимит не задан — fast-path без агрегации.
    if limit is None and max_od is None:
        return CreditCheckResult(
            ok=True,
            current_debt_uzs=Decimal("0"),
            new_sale_uzs=new_sale_uzs,
        )

    report = compute_aging_report(organization, customer_id=str(customer.id))
    if report.rows:
        row = report.rows[0]
        current_debt = row.total
        oldest = row.oldest_overdue_days
    else:
        current_debt = Decimal("0")
        oldest = 0

    result = CreditCheckResult(
        ok=True,
        current_debt_uzs=current_debt,
        oldest_overdue=oldest,
        limit_uzs=limit,
        max_overdue_days=max_od,
        new_sale_uzs=new_sale_uzs,
    )

    # Лимит на сумму
    if limit is not None and (current_debt + new_sale_uzs) > limit:
        result.ok = False
        result.reasons.append(
            f"Превышен кредитный лимит: текущий долг {current_debt:,.0f} + "
            f"новая продажа {new_sale_uzs:,.0f} = "
            f"{(current_debt + new_sale_uzs):,.0f} > лимит {limit:,.0f}."
        )

    # Лимит на просрочку
    if max_od is not None and oldest > max_od:
        result.ok = False
        result.reasons.append(
            f"Превышен срок просрочки: самый старый непогашенный счёт "
            f"просрочен на {oldest} дн (макс. допустимо {max_od} дн)."
        )

    return result
