"""
Парная JournalEntry из StockMovement.

Закрывает дыры аудита: shrinkage_runner, create_movement_for_raw_batch,
create_manual_movement раньше создавали движение по складу, но не
парную проводку в ГК — счёт 10 в Trial Balance уходил «в небо».

Контракт:
    build_subaccounts_for_movement(movement) → (debit_sub, credit_sub)
    create_journal_entry_for_movement(movement, *, ...) → JournalEntry|None

Логика выбора счетов по kind:

| kind                          | Dr (где появилось)        | Cr (откуда пришло)      |
|-------------------------------|---------------------------|--------------------------|
| INCOMING + counterparty       | warehouse_to.gl           | 60.01 (поставщик UZS)    |
| INCOMING без counterparty     | warehouse_to.gl           | 91.01 (прочие доходы)    |
| OUTGOING                      | 91.02 (прочие расходы)    | warehouse_from.gl        |
| WRITE_OFF                     | 91.02                     | warehouse_from.gl        |
| SHRINKAGE                     | 91.02                     | warehouse_from.gl        |
| TRANSFER (разные субсчета)    | warehouse_to.gl           | warehouse_from.gl        |
| TRANSFER (один субсчёт)       | None — JE не нужна, это  внутрисчётный обмен (10.05 ↔ 10.05) |

Если для warehouse_to/warehouse_from не задан default_gl_subaccount —
fallback на nomenclature.default_gl_subaccount → category.default_gl_subaccount.
Если и они NULL — поднимается JournalEntryResolveError (strict=True)
либо логируется и возвращается None (strict=False, для cron'ов).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.common.services.numbering import next_doc_number

from ..models import StockMovement


logger = logging.getLogger(__name__)


class JournalEntryResolveError(ValidationError):
    """План счетов организации не настроен под этот тип движения."""


# Hardcoded — это «системные» субсчета, которые seed-миграция всегда
# создаёт во всех организациях (см. accounting/migrations/0005, 0007).
SUPPLIER_UZS = "60.01"
OTHER_INCOME = "91.01"
OTHER_EXPENSE = "91.02"


@dataclass
class _Resolution:
    debit: Optional[GLSubaccount]
    credit: Optional[GLSubaccount]
    # Если True — это transfer на тот же субсчёт, JE не нужна.
    skip: bool = False


def _get_sub(organization, code: str) -> Optional[GLSubaccount]:
    return GLSubaccount.objects.select_related("account").filter(
        account__organization=organization, code=code,
    ).first()


def _resolve_inventory_sub(
    movement: StockMovement, warehouse_attr: str,
) -> Optional[GLSubaccount]:
    """warehouse.default_gl → nomenclature.default_gl → category.default_gl."""
    wh = getattr(movement, warehouse_attr, None)
    if wh is not None and wh.default_gl_subaccount_id:
        return wh.default_gl_subaccount

    nom = movement.nomenclature
    if nom is not None:
        if getattr(nom, "default_gl_subaccount_id", None):
            return nom.default_gl_subaccount
        category = getattr(nom, "category", None)
        if category is not None and getattr(category, "default_gl_subaccount_id", None):
            return category.default_gl_subaccount

    return None


def build_subaccounts_for_movement(movement: StockMovement) -> _Resolution:
    """
    Определить Dr/Cr субсчета для проводки, либо skip=True если она не
    нужна (внутрисчётный transfer).

    Не пишет в БД. Raises JournalEntryResolveError только если нашлась
    осмысленная пара субсчетов, но какой-то из них не настроен.
    """
    Kind = StockMovement.Kind
    org = movement.organization

    if movement.kind == Kind.INCOMING:
        debit = _resolve_inventory_sub(movement, "warehouse_to")
        if debit is None:
            raise JournalEntryResolveError({
                "warehouse_to": (
                    "Не удалось определить субсчёт учёта прихода: "
                    "ни у склада, ни у номенклатуры, ни у категории "
                    "не задан default_gl_subaccount."
                ),
            })
        if movement.counterparty_id is not None:
            credit = _get_sub(org, SUPPLIER_UZS)
            if credit is None:
                raise JournalEntryResolveError({
                    "__all__": f"Субсчёт {SUPPLIER_UZS} не настроен в плане счетов.",
                })
        else:
            credit = _get_sub(org, OTHER_INCOME)
            if credit is None:
                raise JournalEntryResolveError({
                    "__all__": f"Субсчёт {OTHER_INCOME} не настроен в плане счетов.",
                })
        return _Resolution(debit=debit, credit=credit)

    if movement.kind in (Kind.OUTGOING, Kind.WRITE_OFF, Kind.SHRINKAGE):
        credit = _resolve_inventory_sub(movement, "warehouse_from")
        if credit is None:
            raise JournalEntryResolveError({
                "warehouse_from": (
                    "Не удалось определить субсчёт списания: ни у "
                    "склада, ни у номенклатуры, ни у категории не "
                    "задан default_gl_subaccount."
                ),
            })
        debit = _get_sub(org, OTHER_EXPENSE)
        if debit is None:
            raise JournalEntryResolveError({
                "__all__": f"Субсчёт {OTHER_EXPENSE} не настроен в плане счетов.",
            })
        return _Resolution(debit=debit, credit=credit)

    if movement.kind == Kind.TRANSFER:
        credit = _resolve_inventory_sub(movement, "warehouse_from")
        debit = _resolve_inventory_sub(movement, "warehouse_to")
        if credit is None or debit is None:
            raise JournalEntryResolveError({
                "__all__": (
                    "У одного из складов transfer-движения не задан "
                    "default_gl_subaccount."
                ),
            })
        if credit.id == debit.id:
            # Перемещение в рамках одного субсчёта (например 10.05 → 10.05)
            # — финансово ничего не меняется. JE не создаём.
            return _Resolution(debit=debit, credit=credit, skip=True)
        return _Resolution(debit=debit, credit=credit)

    raise JournalEntryResolveError({"kind": f"Неизвестный тип движения: {movement.kind}."})


def create_journal_entry_for_movement(
    movement: StockMovement,
    *,
    description: Optional[str] = None,
    strict: bool = True,
    user=None,
) -> Optional[JournalEntry]:
    """
    Создать парную JournalEntry для свежесохранённого StockMovement.

    Args:
        movement: уже сохранённый StockMovement.
        description: текст проводки. Default — auto-генерится из движения.
        strict: при True — поднимает JournalEntryResolveError если план
            счетов не настроен. При False — логирует warning и возвращает
            None (для cron-задач: лучше пропустить JE и продолжить, чем
            заблокировать весь обход).
        user: для created_by.

    Returns:
        JournalEntry, или None если skip=True (внутрисчётный transfer)
        или strict=False и план счетов не настроен.
    """
    try:
        res = build_subaccounts_for_movement(movement)
    except JournalEntryResolveError:
        if strict:
            raise
        logger.warning(
            "create_journal_entry_for_movement: skipping JE for SM %s "
            "(%s) — chart-of-accounts misconfigured",
            movement.doc_number, movement.kind,
        )
        return None

    if res.skip:
        return None

    je_number = next_doc_number(
        JournalEntry,
        organization=movement.organization,
        prefix="ПР",
        on_date=movement.date,
    )
    if description is None:
        kind_label = movement.get_kind_display()
        description = (
            f"{kind_label} · СД {movement.doc_number} · "
            f"{movement.nomenclature.sku} × {movement.quantity}"
        )

    je = JournalEntry(
        organization=movement.organization,
        module=movement.module,
        doc_number=je_number,
        entry_date=movement.date,
        description=description[:255],
        debit_subaccount=res.debit,
        credit_subaccount=res.credit,
        amount_uzs=Decimal(movement.amount_uzs),
        source_content_type=ContentType.objects.get_for_model(StockMovement),
        source_object_id=movement.id,
        counterparty=movement.counterparty,
        batch=movement.batch,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()
    return je
