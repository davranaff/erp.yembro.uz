"""
Сервис `confirm_sale` — проведение продажи.

Atomic-транзакция:
    1. Guards: status=DRAFT, есть items, остатки достаточны.
    2. FX-snapshot курса (если currency != UZS).
    3. Генерация doc_number (ПРД-YYYY-NNNNN) если пуст.
    4. По каждой item:
       - cost_per_unit = batch.accumulated_cost_uzs / batch.current_quantity (snapshot ДО декремента)
       - line_cost = quantity * cost_per_unit
       - line_total = quantity * unit_price_uzs
       - StockMovement OUTGOING (списание со склада)
       - Декремент остатка батча; если 0 → COMPLETED
    5. Аггрегаты amount_uzs / cost_uzs / amount_foreign на order.
    6. JournalEntry #1 (выручка): Dr 62.01|62.02 / Cr 90.01.
    7. JournalEntry #2..N (себестоимость): Dr 90.02 / Cr <category-subaccount>
       — раздельные на каждую item (потому что кредитуемый субсчёт зависит от
       категории номенклатуры).
    8. status = CONFIRMED.

После CONFIRMED: snapshot-поля (rate, amount_*) — иммутабельны (enforced
сериализатором + тестом).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.batches.models import Batch
from apps.common.services.numbering import next_doc_number
from apps.currency.selectors import get_rate_for
from apps.warehouses.models import StockMovement

from ..models import SaleItem, SaleOrder


# ─── GL policy ────────────────────────────────────────────────────────────

# Дебет выручки: 62.01 (UZS) или 62.02 (FX)
AR_SUBACCOUNT_UZS = "62.01"
AR_SUBACCOUNT_FX = "62.02"
# Кредит выручки
REVENUE_SUBACCOUNT = "90.01"
# Дебет себестоимости
COGS_SUBACCOUNT = "90.02"
# Дефолтный субсчёт списания если у nomenclature.category нет default_gl_subaccount
DEFAULT_INVENTORY_SUBACCOUNT = "10.01"


class SaleConfirmError(ValidationError):
    """Специфичная ошибка confirm_sale — для отлова в API."""


@dataclass
class SaleConfirmResult:
    order: SaleOrder
    stock_movements: list = field(default_factory=list)
    revenue_journal: Optional[JournalEntry] = None
    cost_journals: list = field(default_factory=list)
    rate_snapshot: Optional[Decimal] = None


def _quantize_money(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_rate(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _get_subaccount(org, code: str) -> GLSubaccount:
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=org, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise SaleConfirmError(
            {
                "__all__": (
                    f"Субсчёт {code} не найден в плане счетов организации "
                    f"{org.code}. Проверьте seed (apps/accounting/migrations/0006)."
                )
            }
        ) from exc


def _resolve_inventory_subaccount(item: SaleItem, org) -> GLSubaccount:
    """
    Кредит для проводки себестоимости (Dr 90.02 / Cr X).

    Источник:
        nomenclature.default_gl_subaccount → category.default_gl_subaccount → 10.01
    """
    nom = item.nomenclature
    if nom.default_gl_subaccount_id:
        return nom.default_gl_subaccount
    if nom.category_id and nom.category.default_gl_subaccount_id:
        return nom.category.default_gl_subaccount
    return _get_subaccount(org, DEFAULT_INVENTORY_SUBACCOUNT)


def _compute_cost_per_unit(item: SaleItem) -> Decimal:
    """
    Себестоимость единицы из источника-партии.

    Для Batch / FeedBatch / VetStockBatch — accumulated_cost (или price) /
    остаток на момент confirm.
    """
    if item.batch_id:
        b = item.batch
        if b.current_quantity and b.current_quantity > 0:
            return _quantize_money(
                Decimal(b.accumulated_cost_uzs) / Decimal(b.current_quantity)
            )
        return Decimal("0.00")
    if item.feed_batch_id:
        fb = item.feed_batch
        # У FeedBatch есть unit_cost_uzs — сразу используем.
        if hasattr(fb, "unit_cost_uzs") and fb.unit_cost_uzs:
            return _quantize_money(Decimal(fb.unit_cost_uzs))
        return Decimal("0.00")
    if item.vet_stock_batch_id:
        vsb = item.vet_stock_batch
        # У VetStockBatch уже есть price_per_unit_uzs (закупочная цена при приёмке).
        return _quantize_money(Decimal(vsb.price_per_unit_uzs or 0))
    return Decimal("0.00")


def _check_and_decrement_source(item: SaleItem, qty: Decimal):
    """
    Списать qty из источника партии, проверив достаточность остатка.
    Возвращает дополнительный объект (Batch / FeedBatch / VetStockBatch)
    для обновления state, если кончился.
    """
    if item.batch_id:
        # select_for_update + select_related("current_module") падает на
        # nullable FK в postgres ("FOR UPDATE cannot be applied to the
        # nullable side of an outer join"). Берём row-lock без join,
        # отдельно подгружаем current_module если понадобится.
        b = Batch.objects.select_for_update().get(pk=item.batch_id)
        if b.state != Batch.State.ACTIVE:
            raise SaleConfirmError(
                {"items": (
                    f"Партия {b.doc_number} не активна "
                    f"({b.get_state_display()}). Продажа невозможна."
                )}
            )
        if Decimal(b.current_quantity) < qty:
            raise SaleConfirmError(
                {"items": (
                    f"Недостаточно остатка в Batch {b.doc_number}: "
                    f"требуется {qty}, доступно {b.current_quantity}."
                )}
            )
        Batch.objects.filter(pk=b.pk).update(
            current_quantity=F("current_quantity") - qty
        )
        b.refresh_from_db(fields=["current_quantity"])
        if b.current_quantity == 0 and b.state == Batch.State.ACTIVE:
            b.state = Batch.State.COMPLETED
            b.completed_at = timezone.localdate()
            b.save(update_fields=["state", "completed_at", "updated_at"])
        return b

    if item.feed_batch_id:
        from apps.feed.models import FeedBatch
        fb = FeedBatch.objects.select_for_update().get(pk=item.feed_batch_id)
        if fb.status != FeedBatch.Status.APPROVED:
            raise SaleConfirmError(
                {"items": (
                    f"Партия комбикорма {fb.doc_number} в статусе "
                    f"{fb.get_status_display()} — продажа возможна только из «Одобрена». "
                    f"Сначала проведите контроль качества партии."
                )}
            )
        if Decimal(fb.current_quantity_kg) < qty:
            raise SaleConfirmError(
                {"items": (
                    f"Недостаточно остатка в FeedBatch {fb.doc_number}: "
                    f"требуется {qty}, доступно {fb.current_quantity_kg}."
                )}
            )
        FeedBatch.objects.filter(pk=fb.pk).update(
            current_quantity_kg=F("current_quantity_kg") - qty
        )
        fb.refresh_from_db(fields=["current_quantity_kg"])
        if fb.current_quantity_kg == 0 and fb.status == FeedBatch.Status.APPROVED:
            fb.status = FeedBatch.Status.DEPLETED
            fb.save(update_fields=["status", "updated_at"])
        return fb

    if item.vet_stock_batch_id:
        from apps.vet.models import VetStockBatch
        vsb = VetStockBatch.objects.select_for_update().get(pk=item.vet_stock_batch_id)
        if Decimal(vsb.current_quantity) < qty:
            raise SaleConfirmError(
                {"items": (
                    f"Недостаточно остатка в VetStockBatch {vsb.doc_number}: "
                    f"требуется {qty}, доступно {vsb.current_quantity}."
                )}
            )
        VetStockBatch.objects.filter(pk=vsb.pk).update(
            current_quantity=F("current_quantity") - qty
        )
        vsb.refresh_from_db(fields=["current_quantity"])
        if vsb.current_quantity == 0 and vsb.status == VetStockBatch.Status.AVAILABLE:
            vsb.status = VetStockBatch.Status.DEPLETED
            vsb.save(update_fields=["status", "updated_at"])
        return vsb

    raise SaleConfirmError({"items": "Item без указания источника партии."})


@transaction.atomic
def confirm_sale(order: SaleOrder, *, user=None) -> SaleConfirmResult:
    """
    Провести продажу. Идемпотентен по статусу: повторный → ValidationError.
    """
    # 1. Lock + reload
    order = SaleOrder.objects.select_for_update().get(pk=order.pk)
    order = SaleOrder.objects.select_related(
        "organization", "module", "warehouse", "customer", "currency",
    ).get(pk=order.pk)

    if order.status != SaleOrder.Status.DRAFT:
        raise SaleConfirmError(
            {"status": (
                f"Провести можно только черновик, текущий статус: "
                f"{order.get_status_display()}."
            )}
        )

    items = list(
        order.items.select_related(
            "nomenclature", "nomenclature__category",
            "nomenclature__default_gl_subaccount",
            "batch", "feed_batch", "vet_stock_batch",
        )
    )
    if not items:
        raise SaleConfirmError({"items": "Нельзя провести продажу без позиций."})

    # 2. FX-snapshot
    #    Приоритет: exchange_rate_override (ручной) → get_rate_for (CBU).
    #    При override — exchange_rate_source остаётся None.
    is_fx = bool(order.currency_id) and order.currency.code.upper() != "UZS"
    rate_obj = None
    if is_fx:
        if order.exchange_rate_override is not None:
            override = Decimal(order.exchange_rate_override)
            if override <= 0:
                raise SaleConfirmError(
                    {"exchange_rate_override": "Курс должен быть больше нуля."}
                )
            rate = _quantize_rate(override)
        else:
            rate_obj = get_rate_for(order.currency.code, order.date)
            rate = _quantize_rate(Decimal(rate_obj.rate) / Decimal(rate_obj.nominal))
    else:
        rate = Decimal("1")

    # 3. doc_number
    if not order.doc_number:
        order.doc_number = next_doc_number(
            SaleOrder, organization=order.organization,
            prefix="ПРД", on_date=order.date,
        )

    # 4. Subaccounts (выручка/AR)
    ar_code = AR_SUBACCOUNT_FX if is_fx else AR_SUBACCOUNT_UZS
    ar_sub = _get_subaccount(order.organization, ar_code)
    revenue_sub = _get_subaccount(order.organization, REVENUE_SUBACCOUNT)
    cogs_sub = _get_subaccount(order.organization, COGS_SUBACCOUNT)

    # 5. По каждой item: cost-snapshot, списание, StockMovement
    total_uzs = Decimal("0")
    total_cost_uzs = Decimal("0")
    total_foreign = Decimal("0") if is_fx else None
    stock_movements = []
    cost_journals = []
    now = timezone.now()
    so_ct = ContentType.objects.get_for_model(SaleOrder)

    for item in items:
        cost_per_unit = _compute_cost_per_unit(item)
        qty = Decimal(item.quantity)

        # Snapshot заполняем ДО списания (cost берётся от текущего остатка)
        item.cost_per_unit_uzs = cost_per_unit
        item.line_cost_uzs = _quantize_money(qty * cost_per_unit)
        item.line_total_uzs = _quantize_money(qty * Decimal(item.unit_price_uzs) * rate)
        item.save(update_fields=[
            "cost_per_unit_uzs", "line_cost_uzs", "line_total_uzs",
        ])

        total_uzs += item.line_total_uzs
        total_cost_uzs += item.line_cost_uzs
        if is_fx:
            line_foreign = _quantize_money(qty * Decimal(item.unit_price_uzs))
            total_foreign += line_foreign

        # Списание из источника
        _check_and_decrement_source(item, qty)

        # StockMovement OUTGOING
        sm = StockMovement(
            organization=order.organization,
            module=order.module,
            doc_number=next_doc_number(
                StockMovement, organization=order.organization,
                prefix="СД", on_date=order.date,
            ),
            kind=StockMovement.Kind.OUTGOING,
            date=now,
            nomenclature=item.nomenclature,
            quantity=qty,
            unit_price_uzs=cost_per_unit,
            amount_uzs=item.line_cost_uzs,
            warehouse_from=order.warehouse,
            warehouse_to=None,
            counterparty=order.customer,
            batch=item.batch,
            source_content_type=so_ct,
            source_object_id=order.id,
            created_by=user,
        )
        sm.full_clean(exclude=None)
        sm.save()
        stock_movements.append(sm)

        # JE #2..N: себестоимость (Dr 90.02 / Cr <inventory-subaccount>)
        cogs_credit = _resolve_inventory_subaccount(item, order.organization)
        cost_je = JournalEntry(
            organization=order.organization,
            module=order.module,
            doc_number=next_doc_number(
                JournalEntry, organization=order.organization,
                prefix="ПР", on_date=order.date,
            ),
            entry_date=order.date,
            description=(
                f"Себестоимость продажи {order.doc_number} · "
                f"{item.nomenclature.sku} × {qty}"
            ),
            debit_subaccount=cogs_sub,
            credit_subaccount=cogs_credit,
            amount_uzs=item.line_cost_uzs,
            source_content_type=so_ct,
            source_object_id=order.id,
            counterparty=order.customer,
            batch=item.batch,
            created_by=user,
        )
        cost_je.full_clean(exclude=None)
        cost_je.save()
        cost_journals.append(cost_je)

    total_uzs = _quantize_money(total_uzs)
    total_cost_uzs = _quantize_money(total_cost_uzs)
    if is_fx:
        total_foreign = _quantize_money(total_foreign)

    # 6. JE #1: выручка (Dr 62.01|02 / Cr 90.01)
    revenue_je = JournalEntry(
        organization=order.organization,
        module=order.module,
        doc_number=next_doc_number(
            JournalEntry, organization=order.organization,
            prefix="ПР", on_date=order.date,
        ),
        entry_date=order.date,
        description=(
            f"Выручка {order.customer.name} · {total_uzs} UZS"
            + (f" ({total_foreign} {order.currency.code} @ {rate})" if is_fx else "")
        ),
        debit_subaccount=ar_sub,
        credit_subaccount=revenue_sub,
        amount_uzs=total_uzs,
        currency=order.currency if is_fx else None,
        amount_foreign=total_foreign if is_fx else None,
        exchange_rate=rate if is_fx else None,
        source_content_type=so_ct,
        source_object_id=order.id,
        counterparty=order.customer,
        created_by=user,
    )
    revenue_je.full_clean(exclude=None)
    revenue_je.save()

    # 7. Финализация order: snapshot-поля
    order.exchange_rate = rate if is_fx else None
    order.exchange_rate_source = rate_obj
    order.amount_foreign = total_foreign if is_fx else None
    order.amount_uzs = total_uzs
    order.cost_uzs = total_cost_uzs
    order.status = SaleOrder.Status.CONFIRMED
    order.save(update_fields=[
        "doc_number",
        "exchange_rate",
        "exchange_rate_source",
        "amount_foreign",
        "amount_uzs",
        "cost_uzs",
        "status",
        "updated_at",
    ])

    audit_log(
        organization=order.organization,
        module=order.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=order,
        action_verb=f"confirmed sale {order.doc_number}",
    )

    return SaleConfirmResult(
        order=order,
        stock_movements=stock_movements,
        revenue_journal=revenue_je,
        cost_journals=cost_journals,
        rate_snapshot=rate if is_fx else None,
    )
