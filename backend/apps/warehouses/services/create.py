"""
Ручное создание StockMovement.

Обычные движения создаются как побочный эффект бизнес-сервисов
(`confirm_purchase`, `accept_transfer` и т.п.) — у них есть `source_content_type`,
по которому видно происхождение.

Здесь создаётся «голое» движение без source — для случаев когда
кладовщик правит остаток вручную (исправление инвентаризации,
ручное списание брака, прямой приход без закупа и т.п.).
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.common.services.numbering import next_doc_number

from ..models import StockMovement
from .balance import compute_warehouse_balance_for_sku
from .journal import create_journal_entry_for_movement


class StockMovementCreateError(ValidationError):
    pass


def _q_money(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _q_qty(v) -> Decimal:
    return Decimal(v).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


@dataclass
class StockMovementCreateResult:
    movement: StockMovement


@transaction.atomic
def create_manual_movement(
    *,
    organization,
    module,
    kind: str,
    nomenclature,
    quantity,
    unit_price_uzs,
    warehouse_from=None,
    warehouse_to=None,
    counterparty=None,
    batch=None,
    date_value=None,
    user=None,
) -> StockMovementCreateResult:
    """
    Создать движение по складу вручную (без привязки к закупу/продаже).

    Проверки:
        - kind ∈ Kind
        - INCOMING требует warehouse_to
        - OUTGOING требует warehouse_from
        - WRITE_OFF требует warehouse_from
        - TRANSFER требует оба
        - quantity > 0, unit_price_uzs >= 0
        - все связанные сущности из этой же organization

    Возвращает:
        StockMovementCreateResult(movement=...)

    Документ-номер генерируется автоматически (СД-YYYY-NNNNN).
    """
    if kind not in StockMovement.Kind.values:
        raise StockMovementCreateError(
            {"kind": f"Неизвестный тип движения: {kind}."}
        )

    qty = _q_qty(quantity)
    price = _q_money(unit_price_uzs)
    if qty <= 0:
        raise StockMovementCreateError(
            {"quantity": "Количество должно быть > 0."}
        )
    if price < 0:
        raise StockMovementCreateError(
            {"unit_price_uzs": "Цена не может быть отрицательной."}
        )

    # Module — системная сущность (feed/vet/incubation/...), org-scope не имеет.
    # Org-валидация делается через Warehouse и Counterparty.

    for wh in (warehouse_from, warehouse_to):
        if wh is not None and wh.organization_id != organization.id:
            raise StockMovementCreateError(
                {"warehouse": "Склад из другой организации."}
            )

    if counterparty is not None and counterparty.organization_id != organization.id:
        raise StockMovementCreateError(
            {"counterparty": "Контрагент из другой организации."}
        )

    if batch is not None and batch.organization_id != organization.id:
        raise StockMovementCreateError(
            {"batch": "Партия из другой организации."}
        )

    # Поставщик для INCOMING опционален: если указан — backend создаёт
    # связанный PurchaseOrder в /purchases (см. _link_to_auto_purchase ниже);
    # если нет — приход остаётся «внутренним» (например, излишки при
    # инвентаризации, безвозмездное поступление, перенос с другого учёта).

    # Гард: для расходных операций требуем чтобы остаток на складе был
    # >= списываемого количества. Раньше можно было через API создать
    # OUTGOING на товар, которого физически нет — balance уходил в
    # минус и GL расходился с физикой. Для TRANSFER гард тот же на
    # warehouse_from (тоже выход). INCOMING всегда разрешён.
    if kind in (
        StockMovement.Kind.OUTGOING,
        StockMovement.Kind.WRITE_OFF,
        StockMovement.Kind.SHRINKAGE,
        StockMovement.Kind.TRANSFER,
    ):
        if warehouse_from is None:
            # Дополнительная страховка к full_clean ниже — иначе compute_balance
            # упадёт на None.
            raise StockMovementCreateError(
                {"warehouse_from": "Для расхода требуется склад-источник."}
            )
        current_balance = compute_warehouse_balance_for_sku(
            warehouse_from, nomenclature,
        )
        if current_balance < qty:
            raise StockMovementCreateError(
                {"quantity": (
                    f"Недостаточно остатка на складе «{warehouse_from.code}»: "
                    f"в наличии {current_balance}, требуется {qty}."
                )}
            )

    when = date_value or timezone.now()

    doc_number = next_doc_number(
        StockMovement,
        organization=organization,
        prefix="СД",
        on_date=when.date() if hasattr(when, "date") else when,
    )

    movement = StockMovement(
        organization=organization,
        module=module,
        doc_number=doc_number,
        kind=kind,
        date=when,
        nomenclature=nomenclature,
        quantity=qty,
        unit_price_uzs=price,
        amount_uzs=_q_money(qty * price),
        warehouse_from=warehouse_from,
        warehouse_to=warehouse_to,
        counterparty=counterparty,
        batch=batch,
        created_by=user,
    )
    movement.full_clean(exclude=None)
    movement.save()

    # Парная JE в ГК (Dr/Cr по матрице из journal.py). Без неё счёт 10
    # в Trial Balance не сходится с физическим складом. strict=False:
    # если в организации не настроен полностью план счетов — не
    # блокируем приход, но пишем warning. Сигналом «настройте план»
    # будет дрифт в ОСВ — оператор увидит и попросит админа.
    create_journal_entry_for_movement(movement, strict=False, user=user)

    # Двунаправленный синк «приход ↔ закуп»: если ручной приход
    # (INCOMING) сделан с указанием поставщика — автоматически создаём
    # связанный PurchaseOrder в статусе CONFIRMED. Это даёт оператору
    # симметрию: PO.confirm создаёт StockMovement, а manual /stock
    # приход создаёт PO. Без дублирования INCOMING — наоборот, новый
    # PO ссылается через source на существующий movement.
    if (
        kind == StockMovement.Kind.INCOMING
        and counterparty is not None
        and warehouse_to is not None
    ):
        _link_to_auto_purchase(movement, user=user)

    return StockMovementCreateResult(movement=movement)


def _link_to_auto_purchase(movement: StockMovement, *, user=None) -> None:
    """
    Создать PurchaseOrder (CONFIRMED, unpaid) из ручного INCOMING-движения
    и перепривязать movement.source → PO. Idempotent: если movement уже
    привязан к источнику — выходим. Без JE/finance операций — это просто
    зеркало для видимости в /purchases, бухгалтерскую проводку оператор
    делает через payment.

    Без него оператор оприходовал товар вручную, а в /purchases список
    был пустой — невозможно было отслеживать долги поставщикам.
    """
    if movement.source_content_type_id or movement.source_object_id:
        return

    from django.contrib.contenttypes.models import ContentType
    from apps.common.services.numbering import next_doc_number
    from apps.purchases.models import PurchaseItem, PurchaseOrder

    when = movement.date.date() if hasattr(movement.date, "date") else movement.date

    po_number = next_doc_number(
        PurchaseOrder,
        organization=movement.organization,
        prefix="ЗК",
        on_date=when,
    )
    po = PurchaseOrder(
        organization=movement.organization,
        module=movement.module,
        doc_number=po_number,
        date=when,
        counterparty=movement.counterparty,
        warehouse=movement.warehouse_to,
        currency=None,
        batch=movement.batch,
        notes=(
            f"Авто-создан из ручного прихода {movement.doc_number} в /stock. "
            f"Оплата — через /finance/cashbox или /purchases."
        ),
        amount_uzs=movement.amount_uzs,
        status=PurchaseOrder.Status.CONFIRMED,
        payment_status=PurchaseOrder.PaymentStatus.UNPAID,
        created_by=user,
    )
    po.save()

    PurchaseItem.objects.create(
        order=po,
        nomenclature=movement.nomenclature,
        quantity=movement.quantity,
        unit_price=movement.unit_price_uzs,
        line_total_uzs=movement.amount_uzs,
        received_qty=movement.quantity,
    )

    # Перепривязываем movement.source → новый PO
    movement.source_content_type = ContentType.objects.get_for_model(PurchaseOrder)
    movement.source_object_id = po.id
    movement.save(update_fields=[
        "source_content_type", "source_object_id", "updated_at",
    ])


def is_manual_movement(movement: StockMovement) -> bool:
    """
    Определяет, было ли движение создано вручную (а не сервисом-источником
    типа confirm_purchase). Только manual движения можно удалять напрямую.
    """
    return movement.source_content_type_id is None and movement.source_object_id is None


@transaction.atomic
def delete_manual_movement(movement: StockMovement, *, user=None) -> None:
    """
    Удалить вручную созданное движение. Движения, порождённые сервисами,
    удалять нельзя — для их отмены нужны соответствующие reverse-сервисы
    (reverse_purchase, reverse_sale и т.д.).
    """
    if not is_manual_movement(movement):
        raise StockMovementCreateError(
            {
                "__all__": (
                    "Это движение создано автоматически по документу-источнику. "
                    "Удаление возможно только через сторно исходного документа."
                )
            }
        )
    movement.delete()


# Безопасный whitelist полей для PATCH manual-движения. Меняют только
# метаданные (когда / кто / какая партия), не трогают суммы/склады/SKU,
# чтобы не пересчитывать остатки.
EDITABLE_MANUAL_FIELDS = ("date", "counterparty", "batch")


@transaction.atomic
def update_manual_movement(
    movement: StockMovement,
    *,
    date_value=None,
    counterparty=None,
    batch=None,
    clear_counterparty: bool = False,
    clear_batch: bool = False,
    user=None,
) -> StockMovement:
    """
    Частично обновить вручную созданное движение. Разрешены ТОЛЬКО:
        - date  — если ошиблись датой
        - counterparty  — привязать/перепривязать к контрагенту
        - batch  — привязать к партии

    Поля quantity / unit_price / amount / kind / nomenclature / warehouse_*
    остаются иммутабельными — для их изменения нужно delete + recreate
    (чтобы остатки и Главная книга пересчитались чисто).

    `clear_counterparty=True` / `clear_batch=True` — явно очистить FK
    (counterparty=None через PATCH в JSON неотличим от «не передано»).

    Возвращает сохранённый movement.

    Raises:
        StockMovementCreateError: если movement не manual или
            переданная связанная сущность из другой организации.
    """
    if not is_manual_movement(movement):
        raise StockMovementCreateError(
            {
                "__all__": (
                    "Это движение создано автоматически по документу-источнику. "
                    "Редактирование возможно только через исходный документ."
                )
            }
        )

    org_id = movement.organization_id
    update_fields: list[str] = []

    if date_value is not None:
        movement.date = date_value
        update_fields.append("date")

    if counterparty is not None:
        if counterparty.organization_id != org_id:
            raise StockMovementCreateError(
                {"counterparty": "Контрагент из другой организации."}
            )
        movement.counterparty = counterparty
        update_fields.append("counterparty")
    elif clear_counterparty:
        movement.counterparty = None
        update_fields.append("counterparty")

    if batch is not None:
        if batch.organization_id != org_id:
            raise StockMovementCreateError(
                {"batch": "Партия из другой организации."}
            )
        movement.batch = batch
        update_fields.append("batch")
    elif clear_batch:
        movement.batch = None
        update_fields.append("batch")

    if not update_fields:
        return movement  # ничего не передано — no-op

    update_fields.append("updated_at")
    movement.save(update_fields=update_fields)
    return movement
