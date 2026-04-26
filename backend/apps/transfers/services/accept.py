"""
Сервис `accept_transfer` — проведение межмодульной передачи.

Два сценария:

1. Poultry batch transfer (transfer.batch != null):
   - Парная проводка через 79.01:
       Dr 79.01 / Cr <source_account>   — отправитель
       Dr <dest_account> / Cr 79.01     — приёмник
   - Парные StockMovement (OUTGOING из from_warehouse, INCOMING в to_warehouse).
   - Закрытие текущего BatchChainStep + открытие нового.
   - Обновление Batch.current_module/block/quantity и accumulated_cost_uzs.
   - BatchCostEntry(category=TRANSFER_IN, amount=cost_uzs).

2. Feed dispatch (transfer.feed_batch != null):
   - Пара StockMovement + пара JournalEntry (Cr 10.05 / Dr 10.05 через 79.01).
   - Декремент feed_batch.current_quantity_kg.
   - Перенос withdrawal_period_ends на всех активных Batch в to_block
     (если feed_batch.is_medicated). Slaughter-guard (Phase 5) автоматически
     заблокирует убой этих партий.

В одной atomic-транзакции. Повторный accept → ValidationError.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type
from decimal import Decimal
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch, BatchChainStep, BatchCostEntry
from apps.common.services.numbering import next_doc_number
from apps.warehouses.models import StockMovement

from ..models import InterModuleTransfer


# ─── GL policy ────────────────────────────────────────────────────────────

# Межмодульный «транзитный» счёт 79.01.
INTER_MODULE_SUBACCOUNT = "79.01"

# Default source/dest subaccount для poultry batch transfers.
# Обычно — 10.02 "Живая птица".
POULTRY_SUBACCOUNT_DEFAULT = "10.02"

# Feed dispatch: 10.05 "Корма".
FEED_SUBACCOUNT = "10.05"


class TransferAcceptError(ValidationError):
    pass


@dataclass
class TransferAcceptResult:
    transfer: InterModuleTransfer
    journal_sender: JournalEntry
    journal_receiver: JournalEntry
    stock_outgoing: StockMovement
    stock_incoming: StockMovement
    affected_batches: list[Batch]


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise TransferAcceptError(
            {"__all__": f"Субсчёт {code} не найден в организации {org.code}."}
        ) from exc


def _find_primary_subaccount_for_batch(transfer: InterModuleTransfer) -> GLSubaccount:
    """
    Субсчёт для оприходования/списания партии.

    Правило: warehouse.default_gl_subaccount → nomenclature.default → 10.02.
    """
    wh = transfer.to_warehouse or transfer.from_warehouse
    if wh and wh.default_gl_subaccount_id:
        return wh.default_gl_subaccount
    nom = transfer.nomenclature
    if nom.default_gl_subaccount_id:
        return nom.default_gl_subaccount
    if nom.category_id and nom.category.default_gl_subaccount_id:
        return nom.category.default_gl_subaccount
    return _get_subaccount(transfer.organization, POULTRY_SUBACCOUNT_DEFAULT)


def _find_feed_subaccount(transfer: InterModuleTransfer) -> GLSubaccount:
    return _get_subaccount(transfer.organization, FEED_SUBACCOUNT)


@transaction.atomic
def submit_transfer(
    transfer: InterModuleTransfer, *, user=None
) -> InterModuleTransfer:
    """DRAFT → AWAITING_ACCEPTANCE (отправитель подтвердил отгрузку)."""
    transfer = InterModuleTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.state != InterModuleTransfer.State.DRAFT:
        raise TransferAcceptError(
            {"state": f"Из статуса {transfer.get_state_display()} нельзя в awaiting."}
        )
    transfer.state = InterModuleTransfer.State.AWAITING_ACCEPTANCE
    transfer.save(update_fields=["state", "updated_at"])
    return transfer


@transaction.atomic
def cancel_transfer(
    transfer: InterModuleTransfer, *, user=None, reason: str = ""
) -> InterModuleTransfer:
    transfer = InterModuleTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.state == InterModuleTransfer.State.POSTED:
        raise TransferAcceptError(
            {"state": "POSTED-передача отменяется только компенсирующей проводкой."}
        )
    transfer.state = InterModuleTransfer.State.CANCELLED
    if reason:
        transfer.review_reason = reason
    transfer.save(update_fields=["state", "review_reason", "updated_at"])
    return transfer


@transaction.atomic
def review_transfer(
    transfer: InterModuleTransfer, *, user=None, reason: str = ""
) -> InterModuleTransfer:
    """AWAITING_ACCEPTANCE → UNDER_REVIEW (приёмщик сомневается)."""
    transfer = InterModuleTransfer.objects.select_for_update().get(pk=transfer.pk)
    if transfer.state != InterModuleTransfer.State.AWAITING_ACCEPTANCE:
        raise TransferAcceptError(
            {"state": f"На review можно только AWAITING_ACCEPTANCE."}
        )
    transfer.state = InterModuleTransfer.State.UNDER_REVIEW
    transfer.review_reason = reason
    transfer.reviewed_by = user
    transfer.save(
        update_fields=["state", "review_reason", "reviewed_by", "updated_at"]
    )
    return transfer


@transaction.atomic
def accept_transfer(
    transfer: InterModuleTransfer, *, user=None
) -> TransferAcceptResult:
    """
    Провести межмодульную передачу.

    Валидные статусы на входе: AWAITING_ACCEPTANCE или UNDER_REVIEW.
    Итог: POSTED с заполненными journal_sender/receiver, stock_outgoing/incoming.
    """
    # 1. Row-lock без select_related
    transfer = InterModuleTransfer.objects.select_for_update().get(pk=transfer.pk)
    transfer = (
        InterModuleTransfer.objects.select_related(
            "organization",
            "from_module",
            "to_module",
            "from_block",
            "to_block",
            "from_warehouse",
            "to_warehouse",
            "nomenclature",
            "nomenclature__category",
            "unit",
            "batch",
            "feed_batch",
        )
        .get(pk=transfer.pk)
    )

    # 2. Статус
    if transfer.state not in (
        InterModuleTransfer.State.AWAITING_ACCEPTANCE,
        InterModuleTransfer.State.UNDER_REVIEW,
    ):
        raise TransferAcceptError(
            {
                "state": (
                    f"Provести можно только AWAITING_ACCEPTANCE или UNDER_REVIEW, "
                    f"сейчас {transfer.get_state_display()}."
                )
            }
        )

    # 3. doc_number — до full_clean, т.к. поле NOT BLANK
    if not transfer.doc_number:
        transfer.doc_number = next_doc_number(
            InterModuleTransfer,
            organization=transfer.organization,
            prefix="ММ",
            on_date=transfer.transfer_date.date() if hasattr(transfer.transfer_date, "date") else transfer.transfer_date,
        )

    # 4. Full clean — проверит XOR batch/feed_batch, block.module, cross-org
    transfer.full_clean(exclude=None)

    # 5. Dispatch по типу
    if transfer.batch_id:
        result = _accept_poultry_transfer(transfer, user=user)
    else:
        result = _accept_feed_dispatch(transfer, user=user)

    # 6. Финализация статуса
    transfer.state = InterModuleTransfer.State.POSTED
    transfer.posted_at = timezone.now()
    transfer.accepted_by = user
    transfer.save(
        update_fields=[
            "doc_number",
            "state",
            "posted_at",
            "accepted_by",
            "journal_sender",
            "journal_receiver",
            "stock_outgoing",
            "stock_incoming",
            "updated_at",
        ]
    )

    audit_log(
        organization=transfer.organization,
        module=transfer.to_module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=transfer,
        action_verb=(
            f"accepted transfer {transfer.doc_number} "
            f"{transfer.from_module.code}→{transfer.to_module.code}"
        ),
    )

    return result


def _accept_poultry_transfer(
    transfer: InterModuleTransfer, *, user
) -> TransferAcceptResult:
    org = transfer.organization
    batch = transfer.batch

    # Guards
    if batch.current_module_id != transfer.from_module_id:
        raise TransferAcceptError(
            {
                "batch": (
                    f"Партия {batch.doc_number} сейчас в модуле "
                    f"{batch.current_module.code if batch.current_module_id else None}, "
                    f"а передача заявлена из {transfer.from_module.code}."
                )
            }
        )

    inter_sub = _get_subaccount(org, INTER_MODULE_SUBACCOUNT)
    primary_sub = _find_primary_subaccount_for_batch(transfer)

    # StockMovement: OUTGOING
    sm_out = _create_stock_movement(
        transfer,
        kind=StockMovement.Kind.OUTGOING,
        warehouse_to=None,
        warehouse_from=transfer.from_warehouse,
        user=user,
    )
    # StockMovement: INCOMING
    sm_in = _create_stock_movement(
        transfer,
        kind=StockMovement.Kind.INCOMING,
        warehouse_to=transfer.to_warehouse,
        warehouse_from=None,
        user=user,
    )

    # JournalEntry: sender (Dr 79.01 / Cr primary)
    je_sender = _create_journal_entry(
        transfer,
        debit_sub=inter_sub,
        credit_sub=primary_sub,
        module=transfer.from_module,
        description=(
            f"Межмодульная передача {transfer.doc_number} · "
            f"отгрузка {batch.doc_number} из {transfer.from_module.code}"
        ),
        user=user,
    )
    # JournalEntry: receiver (Dr primary / Cr 79.01)
    je_receiver = _create_journal_entry(
        transfer,
        debit_sub=primary_sub,
        credit_sub=inter_sub,
        module=transfer.to_module,
        description=(
            f"Межмодульная передача {transfer.doc_number} · "
            f"приём {batch.doc_number} в {transfer.to_module.code}"
        ),
        user=user,
    )

    # Закрыть текущий chain step
    current_step = (
        BatchChainStep.objects.filter(batch=batch, exited_at__isnull=True)
        .order_by("-sequence")
        .first()
    )
    now = transfer.posted_at or timezone.now()
    new_accum = batch.accumulated_cost_uzs + transfer.cost_uzs
    if current_step:
        current_step.exited_at = now
        current_step.quantity_out = transfer.quantity
        current_step.accumulated_cost_at_exit = batch.accumulated_cost_uzs
        current_step.transfer_out = transfer
        current_step.save(
            update_fields=[
                "exited_at",
                "quantity_out",
                "accumulated_cost_at_exit",
                "transfer_out",
                "updated_at",
            ]
        )
        next_seq = current_step.sequence + 1
    else:
        next_seq = 1

    # Открыть новый chain step
    new_step = BatchChainStep.objects.create(
        batch=batch,
        sequence=next_seq,
        module=transfer.to_module,
        block=transfer.to_block,
        entered_at=now,
        quantity_in=transfer.quantity,
        transfer_in=transfer,
    )

    # Обновить Batch
    batch.current_module = transfer.to_module
    batch.current_block = transfer.to_block
    batch.current_quantity = transfer.quantity
    batch.accumulated_cost_uzs = new_accum
    batch.save(
        update_fields=[
            "current_module",
            "current_block",
            "current_quantity",
            "accumulated_cost_uzs",
            "updated_at",
        ]
    )

    # BatchCostEntry — transfer-in cost
    BatchCostEntry.objects.create(
        batch=batch,
        category=BatchCostEntry.Category.TRANSFER_IN,
        amount_uzs=Decimal("0"),  # перенос, не новая затрата; но регистрируем событие
        description=f"Приход из {transfer.from_module.code} · передача {transfer.doc_number}",
        occurred_at=now,
        module=transfer.to_module,
        source_content_type=ContentType.objects.get_for_model(InterModuleTransfer),
        source_object_id=transfer.id,
        created_by=user,
    )

    # Привязать FK-ссылки к transfer
    transfer.journal_sender = je_sender
    transfer.journal_receiver = je_receiver
    transfer.stock_outgoing = sm_out
    transfer.stock_incoming = sm_in

    return TransferAcceptResult(
        transfer=transfer,
        journal_sender=je_sender,
        journal_receiver=je_receiver,
        stock_outgoing=sm_out,
        stock_incoming=sm_in,
        affected_batches=[batch],
    )


def _accept_feed_dispatch(
    transfer: InterModuleTransfer, *, user
) -> TransferAcceptResult:
    org = transfer.organization
    feed_batch = transfer.feed_batch

    # Guards
    if feed_batch.current_quantity_kg < transfer.quantity:
        raise TransferAcceptError(
            {
                "quantity": (
                    f"На партии корма {feed_batch.doc_number} всего "
                    f"{feed_batch.current_quantity_kg} кг, требуется {transfer.quantity}."
                )
            }
        )

    inter_sub = _get_subaccount(org, INTER_MODULE_SUBACCOUNT)
    feed_sub = _find_feed_subaccount(transfer)

    # StockMovement OUTGOING из feed-склада
    sm_out = _create_stock_movement(
        transfer,
        kind=StockMovement.Kind.OUTGOING,
        warehouse_to=None,
        warehouse_from=transfer.from_warehouse,
        user=user,
    )
    sm_in = _create_stock_movement(
        transfer,
        kind=StockMovement.Kind.INCOMING,
        warehouse_to=transfer.to_warehouse,
        warehouse_from=None,
        user=user,
    )

    # JE пара через 79.01
    je_sender = _create_journal_entry(
        transfer,
        debit_sub=inter_sub,
        credit_sub=feed_sub,
        module=transfer.from_module,
        description=(
            f"Отгрузка корма {feed_batch.doc_number} · "
            f"передача {transfer.doc_number}"
        ),
        user=user,
    )
    je_receiver = _create_journal_entry(
        transfer,
        debit_sub=feed_sub,
        credit_sub=inter_sub,
        module=transfer.to_module,
        description=(
            f"Приём корма {feed_batch.doc_number} в {transfer.to_module.code} · "
            f"передача {transfer.doc_number}"
        ),
        user=user,
    )

    # Декремент current_quantity на feed batch (через F() — безопасно)
    type(feed_batch).objects.filter(pk=feed_batch.pk).update(
        current_quantity_kg=F("current_quantity_kg") - transfer.quantity
    )
    feed_batch.refresh_from_db(fields=["current_quantity_kg"])

    # Перенос withdrawal_period_ends на активные Batch в to_block/to_module
    affected_batches: list[Batch] = []
    if feed_batch.is_medicated and feed_batch.withdrawal_period_ends:
        consumer_batches = Batch.objects.select_for_update().filter(
            organization=org,
            current_module=transfer.to_module,
            state=Batch.State.ACTIVE,
        )
        if transfer.to_block_id:
            consumer_batches = consumer_batches.filter(current_block=transfer.to_block)

        new_end = feed_batch.withdrawal_period_ends
        for b in consumer_batches:
            if b.withdrawal_period_ends is None or new_end > b.withdrawal_period_ends:
                b.withdrawal_period_ends = new_end
                b.save(update_fields=["withdrawal_period_ends", "updated_at"])
                affected_batches.append(b)

    transfer.journal_sender = je_sender
    transfer.journal_receiver = je_receiver
    transfer.stock_outgoing = sm_out
    transfer.stock_incoming = sm_in

    return TransferAcceptResult(
        transfer=transfer,
        journal_sender=je_sender,
        journal_receiver=je_receiver,
        stock_outgoing=sm_out,
        stock_incoming=sm_in,
        affected_batches=affected_batches,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────


def _create_stock_movement(
    transfer: InterModuleTransfer,
    *,
    kind: str,
    warehouse_from,
    warehouse_to,
    user,
) -> StockMovement:
    org = transfer.organization
    is_outgoing = kind == StockMovement.Kind.OUTGOING
    module = transfer.from_module if is_outgoing else transfer.to_module
    doc_number = next_doc_number(
        StockMovement,
        organization=org,
        prefix="СД",
        on_date=transfer.transfer_date.date() if hasattr(transfer.transfer_date, "date") else transfer.transfer_date,
    )
    unit_price = (
        transfer.cost_uzs / transfer.quantity if transfer.quantity else Decimal("0")
    )
    sm = StockMovement(
        organization=org,
        module=module,
        doc_number=doc_number,
        kind=kind,
        date=transfer.transfer_date,
        nomenclature=transfer.nomenclature,
        quantity=transfer.quantity,
        unit_price_uzs=unit_price.quantize(Decimal("0.01")),
        amount_uzs=transfer.cost_uzs,
        warehouse_from=warehouse_from,
        warehouse_to=warehouse_to,
        batch=transfer.batch,  # feed_batch → None (модель stock не знает feed_batch)
        source_content_type=ContentType.objects.get_for_model(InterModuleTransfer),
        source_object_id=transfer.id,
        created_by=user,
    )
    sm.full_clean(exclude=None)
    sm.save()
    return sm


def _create_journal_entry(
    transfer: InterModuleTransfer,
    *,
    debit_sub,
    credit_sub,
    module,
    description: str,
    user,
) -> JournalEntry:
    org = transfer.organization
    entry_date = (
        transfer.transfer_date.date()
        if hasattr(transfer.transfer_date, "date")
        else transfer.transfer_date
    )
    doc_number = next_doc_number(
        JournalEntry, organization=org, prefix="ПР", on_date=entry_date
    )
    je = JournalEntry(
        organization=org,
        module=module,
        doc_number=doc_number,
        entry_date=entry_date,
        description=description,
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=transfer.cost_uzs,
        source_content_type=ContentType.objects.get_for_model(InterModuleTransfer),
        source_object_id=transfer.id,
        batch=transfer.batch,  # для poultry; для feed остаётся None
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()
    return je
