"""
Сервис `confirm_purchase` — проведение закупа.

Что делает в одной atomic-транзакции:
    1. Проверяет статус (только DRAFT → CONFIRMED).
    2. Снимает FX-snapshot курса (если currency задан и != UZS).
    3. Пересчитывает суммы строк и агрегаты заказа.
    4. Генерирует doc_number если ещё не задан.
    5. Создаёт StockMovement(kind=INCOMING) на весь закуп (агрегированный
       по warehouse — один приход на заказ; детализация — PurchaseItem).
    6. Создаёт JournalEntry (Dr 10.XX / Cr 60.01|60.02) с FX-snapshot.
    7. Переводит PurchaseOrder.status = CONFIRMED.

Возвращает словарь { order, stock_movement, journal_entry } для использования
в тестах и API-response.

Ключевой инвариант: после CONFIRMED поля snapshot-а (exchange_rate,
amount_uzs, amount_foreign, line_total_*) — неизменяемы. Enforcement
сейчас на уровне сервиса (не даст вызвать confirm повторно) + admin
readonly. Попытки прямого SQL-апдейта не защищены — это нормально для
текущей фазы.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.accounting.models import GLSubaccount, JournalEntry
from apps.audit.models import AuditLog
from apps.audit.services.writer import audit_log
from apps.currency.selectors import get_rate_for
from apps.warehouses.models import StockMovement

from apps.common.services.numbering import next_doc_number

from ..models import PurchaseOrder


# ─── GL-субсчета, используемые при проведении ─────────────────────────────
#
# Упрощённая политика:
#   Dr — default_gl_subaccount у warehouse → fallback у nomenclature →
#        fallback у category → ошибка.
#   Cr — "60.02" если закуп в валюте, "60.01" если в UZS.
#
# Коды 60.01 / 60.02 приходят из seed-миграции accounting/0005.
CR_SUBACCOUNT_UZS = "60.01"
CR_SUBACCOUNT_FX = "60.02"


class PurchaseConfirmError(ValidationError):
    """Специфичная ошибка конфирма — чтобы в API её можно было поймать отдельно."""


@dataclass
class PurchaseConfirmResult:
    order: PurchaseOrder
    stock_movement: StockMovement
    journal_entry: JournalEntry
    rate_snapshot: Optional[Decimal]


def _resolve_debit_subaccount(order: PurchaseOrder) -> GLSubaccount:
    """
    Найти дебетовый субсчёт для прихода.

    Правило: warehouse.default_gl_subaccount → первый item.nomenclature
    (default_gl_subaccount или category.default_gl_subaccount).
    Все items одного закупа обычно ложатся на один субсчёт (10.01 сырьё
    для feed-модуля, 10.03 ветпрепараты и т.п.). Если в закупе позиции
    ведут на РАЗНЫЕ субсчета — это ошибка модели данных, но сейчас не
    ловим: сервис берёт субсчёт первой позиции и валит 60.XX на него.
    """
    if order.warehouse_id and order.warehouse.default_gl_subaccount_id:
        return order.warehouse.default_gl_subaccount

    first_item = order.items.select_related("nomenclature", "nomenclature__category").first()
    if first_item:
        nom = first_item.nomenclature
        if nom.default_gl_subaccount_id:
            return nom.default_gl_subaccount
        if nom.category_id and nom.category.default_gl_subaccount_id:
            return nom.category.default_gl_subaccount

    raise PurchaseConfirmError(
        {
            "__all__": (
                "Не удалось определить субсчёт учёта: ни у склада, "
                "ни у номенклатуры, ни у категории не задан default_gl_subaccount."
            )
        }
    )


def _resolve_credit_subaccount(order: PurchaseOrder, *, in_currency: bool) -> GLSubaccount:
    code = CR_SUBACCOUNT_FX if in_currency else CR_SUBACCOUNT_UZS
    try:
        return GLSubaccount.objects.select_related("account").get(
            account__organization=order.organization, code=code
        )
    except GLSubaccount.DoesNotExist as exc:
        raise PurchaseConfirmError(
            {
                "__all__": (
                    f"Субсчёт {code} не найден в плане счетов организации "
                    f"{order.organization.code}. Проверьте seed плана счетов."
                )
            }
        ) from exc


def _quantize_money(value: Decimal) -> Decimal:
    """Округление денежных сумм до 2 знаков после запятой."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantize_rate(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


@transaction.atomic
def confirm_purchase(
    order: PurchaseOrder, *, user=None
) -> PurchaseConfirmResult:
    """
    Провести закуп. Идемпотентен по статусу: повторный вызов на CONFIRMED
    → ValidationError.

    Args:
        order: PurchaseOrder в статусе DRAFT.
        user: User, который проводит (для created_by у связанных документов).

    Returns:
        PurchaseConfirmResult(order, stock_movement, journal_entry, rate_snapshot).

    Raises:
        PurchaseConfirmError: при любых бизнес-проблемах.
    """
    # 1. Re-fetch с блокировкой — чтобы не было race с параллельным confirm.
    # В PostgreSQL FOR UPDATE не совместим с outer-join на nullable FK,
    # поэтому берём row-lock без select_related, а связанные объекты
    # подтягиваем отдельно.
    order = PurchaseOrder.objects.select_for_update().get(pk=order.pk)
    order = (
        PurchaseOrder.objects.select_related(
            "organization", "warehouse", "counterparty", "currency"
        ).get(pk=order.pk)
    )

    # 2. Статус
    if order.status != PurchaseOrder.Status.DRAFT:
        raise PurchaseConfirmError(
            {
                "status": (
                    f"Провести можно только черновик, текущий статус: "
                    f"{order.get_status_display()}."
                )
            }
        )

    # 3. Items обязательны
    items = list(order.items.select_related("nomenclature"))
    if not items:
        raise PurchaseConfirmError(
            {"items": "Нельзя провести закуп без позиций."}
        )

    # 4. FX snapshot
    #    Приоритет: exchange_rate_override (ручной) → get_rate_for (CBU).
    #    Если override задан — exchange_rate_source остаётся NULL: это явный
    #    маркер, что курс ввёл человек, а не получен из ЦБ.
    is_fx = bool(order.currency_id) and order.currency.code.upper() != "UZS"
    rate: Decimal
    rate_source = None
    if is_fx:
        if order.exchange_rate_override is not None:
            override = Decimal(order.exchange_rate_override)
            if override <= 0:
                raise PurchaseConfirmError(
                    {"exchange_rate_override": "Курс должен быть больше нуля."}
                )
            rate = _quantize_rate(override)
        else:
            rate_obj = get_rate_for(order.currency.code, order.date)
            # В CBU Nominal — это «за сколько единиц валюты указан курс».
            # rate_per_unit = rate / nominal.
            rate = _quantize_rate(Decimal(rate_obj.rate) / Decimal(rate_obj.nominal))
            rate_source = rate_obj
    else:
        rate = Decimal("1")

    # 5. Пересчёт строк
    total_uzs = Decimal("0")
    total_foreign = Decimal("0")
    for item in items:
        line_total_in_currency = Decimal(item.quantity) * Decimal(item.unit_price)
        line_uzs = _quantize_money(line_total_in_currency * rate)

        if is_fx:
            item.line_total_foreign = _quantize_money(line_total_in_currency)
            total_foreign += item.line_total_foreign
        else:
            item.line_total_foreign = None
        item.line_total_uzs = line_uzs
        item.save(update_fields=["line_total_foreign", "line_total_uzs"])

        total_uzs += line_uzs

    total_uzs = _quantize_money(total_uzs)
    if is_fx:
        total_foreign = _quantize_money(total_foreign)

    # 6. doc_number если пустой
    if not order.doc_number:
        order.doc_number = next_doc_number(
            PurchaseOrder,
            organization=order.organization,
            prefix="ЗК",
            on_date=order.date,
        )

    # 7. Субсчета
    debit_sub = _resolve_debit_subaccount(order)
    credit_sub = _resolve_credit_subaccount(order, in_currency=is_fx)

    # 8. StockMovement (INCOMING на весь закуп, агрегированный по warehouse)
    #    При необходимости в будущем можно делать N движений — по одному на каждый item.
    sm_number = next_doc_number(
        StockMovement,
        organization=order.organization,
        prefix="СД",
        on_date=order.date,
    )
    now = timezone.now()
    # Для StockMovement нужна позиционная модель — одно движение на закуп
    # с первой позицией (MVP). Полноценная детализация — когда будем
    # делать items-level movements.
    main_item = items[0]
    # Это упрощение: мы агрегируем ВСЁ в 1 движение на 1 номенклатуру.
    # Если позиций больше одной с разными SKU, этого недостаточно.
    # Для корректного MVP создадим N движений — по одному на каждую позицию.
    stock_movements = []
    for idx, item in enumerate(items):
        unit_price_uzs = _quantize_money(
            Decimal(item.unit_price) * rate
        )
        amount_uzs = _quantize_money(Decimal(item.quantity) * unit_price_uzs)
        sm = StockMovement(
            organization=order.organization,
            module=order.module,
            doc_number=(
                sm_number
                if idx == 0
                else next_doc_number(
                    StockMovement,
                    organization=order.organization,
                    prefix="СД",
                    on_date=order.date,
                )
            ),
            kind=StockMovement.Kind.INCOMING,
            date=now,
            nomenclature=item.nomenclature,
            quantity=item.quantity,
            unit_price_uzs=unit_price_uzs,
            amount_uzs=amount_uzs,
            warehouse_to=order.warehouse,
            counterparty=order.counterparty,
            batch=order.batch,
            source_content_type=ContentType.objects.get_for_model(PurchaseOrder),
            source_object_id=order.id,
            created_by=user,
        )
        sm.full_clean(exclude=None)
        sm.save()
        stock_movements.append(sm)
    primary_movement = stock_movements[0]

    # 9. JournalEntry (Dr 10.XX / Cr 60.XX)
    je_number = next_doc_number(
        JournalEntry,
        organization=order.organization,
        prefix="ПР",
        on_date=order.date,
    )
    je = JournalEntry(
        organization=order.organization,
        module=order.module,
        doc_number=je_number,
        entry_date=order.date,
        description=(
            f"Закуп {order.counterparty.name} · {total_uzs} UZS"
            + (f" ({total_foreign} {order.currency.code} @ {rate})" if is_fx else "")
        ),
        debit_subaccount=debit_sub,
        credit_subaccount=credit_sub,
        amount_uzs=total_uzs,
        currency=order.currency if is_fx else None,
        amount_foreign=total_foreign if is_fx else None,
        exchange_rate=rate if is_fx else None,
        source_content_type=ContentType.objects.get_for_model(PurchaseOrder),
        source_object_id=order.id,
        counterparty=order.counterparty,
        batch=order.batch,
        created_by=user,
    )
    je.full_clean(exclude=None)
    je.save()

    # 10. Финализация заказа — snapshot-поля фиксируются здесь
    order.exchange_rate = rate if is_fx else None
    order.exchange_rate_source = rate_source
    order.amount_foreign = total_foreign if is_fx else None
    order.amount_uzs = total_uzs
    order.status = PurchaseOrder.Status.CONFIRMED
    order.save(
        update_fields=[
            "doc_number",
            "exchange_rate",
            "exchange_rate_source",
            "amount_foreign",
            "amount_uzs",
            "status",
            "updated_at",
        ]
    )

    audit_log(
        organization=order.organization,
        module=order.module,
        actor=user,
        action=AuditLog.Action.POST,
        entity=order,
        action_verb=f"confirmed purchase {order.doc_number}",
    )

    return PurchaseConfirmResult(
        order=order,
        stock_movement=primary_movement,
        journal_entry=je,
        rate_snapshot=rate if is_fx else None,
    )
