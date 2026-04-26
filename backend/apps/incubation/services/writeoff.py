"""
Общий helper для списания отхода яиц в бухгалтерии.

Используется в `hatch_incubation_run` (discarded_count при выводе) и в
`cancel_incubation_run` (остаток при отмене).

Проводка:
    Дт 91.02 (Прочие расходы) / Кт 20.03 (НЗП инкубации)
    на сумму (cost_per_egg × eggs_to_writeoff).

cost_per_egg вычисляется ДО закрытия egg_batch:
    cost_per_egg = egg_batch.accumulated_cost_uzs / egg_batch.current_quantity

Важно: списание должно происходить ДО зануления egg_batch.current_quantity,
иначе cost_per_egg = деление на ноль.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number


# Субсчета GL (см. apps/accounting/migrations/)
INCUBATION_WIP_CODE = "20.03"    # НЗП инкубации
OPEX_OUT_CODE = "91.02"          # Прочие расходы


class WriteoffError(ValidationError):
    pass


@dataclass
class WriteoffResult:
    journal_entry: Optional[JournalEntry]
    amount_uzs: Decimal
    eggs_count: int
    cost_per_egg: Decimal


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise WriteoffError(
            {"__all__": f"Субсчёт {code} не найден в плане счетов организации {org.code}."}
        ) from exc


@transaction.atomic
def create_writeoff_je(
    *,
    run,
    egg_batch: Batch,
    eggs_to_writeoff: int,
    on_date,
    description_prefix: str,
    user=None,
) -> WriteoffResult:
    """
    Создаёт JournalEntry Дт 91.02 / Кт 20.03 на стоимость eggs_to_writeoff яиц.

    Args:
        run: IncubationRun (для source_content_type/source_object_id).
        egg_batch: текущая egg_batch (для получения accumulated_cost и qty).
        eggs_to_writeoff: сколько яиц списываем.
        on_date: entry_date для JE.
        description_prefix: префикс описания.

    Returns:
        WriteoffResult с JournalEntry (None если eggs_to_writeoff==0).
    """
    if eggs_to_writeoff <= 0:
        return WriteoffResult(
            journal_entry=None,
            amount_uzs=Decimal("0"),
            eggs_count=0,
            cost_per_egg=Decimal("0"),
        )

    org = run.organization
    qty = Decimal(egg_batch.current_quantity)
    if qty <= 0:
        # Нечего списывать (egg_batch уже пуст)
        return WriteoffResult(
            journal_entry=None,
            amount_uzs=Decimal("0"),
            eggs_count=0,
            cost_per_egg=Decimal("0"),
        )

    cost_per_egg = (Decimal(egg_batch.accumulated_cost_uzs) / qty).quantize(Decimal("0.01"))
    writeoff = eggs_to_writeoff if eggs_to_writeoff <= qty else int(qty)
    total = (cost_per_egg * Decimal(writeoff)).quantize(Decimal("0.01"))

    if total <= 0:
        return WriteoffResult(
            journal_entry=None,
            amount_uzs=Decimal("0"),
            eggs_count=writeoff,
            cost_per_egg=cost_per_egg,
        )

    debit_sub = _get_subaccount(org, OPEX_OUT_CODE)
    credit_sub = _get_subaccount(org, INCUBATION_WIP_CODE)

    run_ct = ContentType.objects.get_for_model(run.__class__)
    je_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=on_date,
    )
    je = JournalEntry(
        organization=org,
        module=run.module,
        doc_number=je_number,
        entry_date=on_date,
        description=(
            f"{description_prefix} · {writeoff} яиц × {cost_per_egg} = {total}"
        ),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=total,
        source_content_type=run_ct,
        source_object_id=run.id,
        batch=egg_batch,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # Уменьшаем accumulated_cost egg_batch: списанная часть не перейдёт на chick_batch.
    new_cost = Decimal(egg_batch.accumulated_cost_uzs) - total
    if new_cost < 0:
        new_cost = Decimal("0")
    Batch.objects.filter(pk=egg_batch.pk).update(accumulated_cost_uzs=new_cost)
    egg_batch.refresh_from_db(fields=["accumulated_cost_uzs"])

    return WriteoffResult(
        journal_entry=je,
        amount_uzs=total,
        eggs_count=writeoff,
        cost_per_egg=cost_per_egg,
    )
