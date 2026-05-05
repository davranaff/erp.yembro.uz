"""
Уведомление-оркестраторы: одно событие → веер задач в celery с разными
аудиториями и текстами.

Зачем: раньше views сами решали кому слать (и часто шлали только админам
sales). Бизнес хочет «при каждом платеже — клиент + админ организации +
head соответствующего модуля». Концентрируем эту логику здесь, чтобы
view-код оставался тонким и не дублировался в payments/sales/purchases.
"""
from __future__ import annotations

import logging
from decimal import Decimal


logger = logging.getLogger(__name__)


def notify_credit_status_change(customer, *, was_ok: bool, is_ok: bool, reasons: list[str] | None = None) -> None:
    """Шлём клиенту pus если его кредит-статус ИЗМЕНИЛСЯ.

    - was_ok=True → is_ok=False: клиент только что заблокирован.
    - was_ok=False → is_ok=True: клиент только что разблокирован.
    - same → ничего не шлём (без шума).

    Вызывается из confirm_sale (новая продажа могла переполнить лимит)
    и из record_payment (оплата могла снять блок).
    """
    from .. import notifications as fmt
    from ..tasks import notify_counterparty_task

    if was_ok == is_ok:
        return  # ничего не изменилось — молчим

    org_id = str(customer.organization_id)
    cp_id = str(customer.id)

    if not is_ok:
        # Только что заблокирован
        text_lines = [
            "🚫 <b>Holatingiz: bloklangan</b>",
            f"<i>{customer.name}</i>",
            "",
            "Yangi xaridlar vaqtincha to'xtatildi.",
        ]
        if reasons:
            text_lines.append("")
            text_lines.append("<b>Sabab:</b>")
            for r in reasons:
                text_lines.append(f"• {r}")
        text_lines.append("")
        text_lines.append(
            "💳 Qarzni to'lashdan so'ng holatingiz avtomatik ravishda "
            "qayta «faol» bo'ladi."
        )
        text = "\n".join(text_lines)
    else:
        # Только что разблокирован
        text = (
            f"✅ <b>Holatingiz qayta faol!</b>\n"
            f"<i>{customer.name}</i>\n\n"
            f"Endi yangi xaridlar mumkin."
        )

    try:
        notify_counterparty_task.delay(text, org_id, cp_id)
    except Exception:  # noqa: BLE001
        logger.exception("notify_credit_status_change: notify failed")


def notify_payment_event(payment, *, related_order=None) -> None:
    """Один платёж → 3 (или 2) уведомления:

    1. **Клиент** (counterparty linked to TG): «to'lov qabul qilindi» —
       только для входящих (direction=in). Для outgoing к поставщику —
       шлём в TgLink контрагента-поставщика, если привязан.
    2. **Админы организации** (module_code='admin', level >= r) — общий
       канал «всё что движется по деньгам».
    3. **Head соответствующего модуля** — sales для in-платежа, purchases
       для out (level >= admin, чтобы не спамить рядовых менеджеров).

    Все вызовы через .delay — view возвращает ответ моментально, никаких
    блокировок на TG-API.
    """
    from .. import notifications as fmt
    from ..tasks import notify_admins_task, notify_counterparty_task

    org_id = str(payment.organization_id)

    # 1. Клиент / поставщик (counterparty notification)
    if payment.counterparty_id:
        if payment.direction == "in":
            text_client = fmt.fmt_payment_received_for_client(payment, related_order)
        else:
            # Outgoing: «sizga to'lov yuborildi» (для поставщика). Если
            # related_order это PurchaseOrder — упомянем его номер.
            text_client = (
                f"💸 <b>To'lov yuborildi</b>\n"
                f"💰 Summa: <b>{fmt._fmt_money(payment.amount_uzs)} so'm</b>\n"
                f"💳 Kanal: {payment.get_channel_display()}\n"
                f"📅 Sana: {payment.date}"
            )
            if related_order is not None:
                text_client += f"\n📄 Hujjat: <code>{related_order.doc_number}</code>"
        try:
            notify_counterparty_task.delay(
                text_client, org_id, str(payment.counterparty_id),
            )
        except Exception:  # noqa: BLE001
            logger.exception("notify_payment_event: client notify failed")

    # 2 + 3. Сотрудники: общий fmt_payment_posted одним вызовом для obox
    # аудиторий — admin (org-wide owner) И source-модуль (head sales/purchases).
    # Используем notify_admins_task с modules=[...] — OR-логика, дедупликация
    # по chat_id (раньше делали 2 отдельных task'а → owner получал дубль).
    text_staff = fmt.fmt_payment_posted(payment)
    primary_module = "sales" if payment.direction == "in" else "purchases"
    try:
        notify_admins_task.delay(
            text_staff, org_id,
            modules=["admin", primary_module],
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_payment_event: staff notify failed")


def notify_sale_event(order) -> None:
    """Подтверждённая продажа → клиент + админы sales + head'ы source-модулей
    с детализацией. Покрывает требование «при продаже клиент видит
    оформление, админ видит сводку, head feed/vet видит свои позиции».
    """
    from .. import notifications as fmt
    from ..tasks import notify_admins_task, notify_counterparty_task

    org_id = str(order.organization_id)

    # 1. Клиент — «buyurtmangiz rasmiylashtirildi»
    if order.customer_id:
        try:
            notify_counterparty_task.delay(
                fmt.fmt_sale_confirmed_for_client(order),
                org_id, str(order.customer_id),
            )
        except Exception:  # noqa: BLE001
            logger.exception("notify_sale_event: client notify failed")

    # 2. Админы организации + sales-head — общая сводка одним вызовом
    # с дедупом, чтобы owner не получал её 2 раза.
    try:
        notify_admins_task.delay(
            fmt.fmt_sale_confirmed(order), org_id,
            modules=["admin", "sales"],
        )
    except Exception:  # noqa: BLE001
        logger.exception("notify_sale_event: sales admin notify failed")

    # 3. Head source-модулей — детализация по их позициям (feed/vet/др.)
    items_by_module: dict = {}
    items = order.items.select_related(
        "batch__current_module",
        "feed_batch__recipe_version__recipe",
        "feed_bag_lot__recipe_version__recipe",
        "vet_stock_batch__drug__nomenclature",
        "vet_accessory__nomenclature",
    )
    for it in items:
        if it.feed_batch_id or it.feed_bag_lot_id:
            code = "feed"
        elif it.vet_stock_batch_id or it.vet_accessory_id:
            code = "vet"
        elif it.batch_id and it.batch.current_module_id:
            code = it.batch.current_module.code
        else:
            continue
        items_by_module.setdefault(code, []).append(it)

    for module_code, mod_items in items_by_module.items():
        try:
            if module_code == "feed":
                text = fmt.fmt_sale_for_feed_module(order, mod_items)
            elif module_code == "vet":
                text = fmt.fmt_sale_for_vet_module(order, mod_items)
            else:
                label = (
                    mod_items[0].batch.current_module.name
                    if mod_items[0].batch_id else module_code
                )
                text = fmt.fmt_sale_for_generic_module(order, mod_items, label)
            notify_admins_task.delay(text, org_id, module_code)
        except Exception:  # noqa: BLE001
            logger.exception(
                "notify_sale_event: module=%s notify failed", module_code,
            )


def notify_purchase_event(order) -> None:
    """Проведённый закуп → админам организации + head'у purchases.

    Один вызов с modules=["admin", "purchases"] — owner получит ОДНО
    сообщение даже если он admin к обоим (раньше было 2 одинаковых).
    """
    from .. import notifications as fmt
    from ..tasks import notify_admins_task

    org_id = str(order.organization_id)
    text = fmt.fmt_purchase_confirmed(order)
    try:
        notify_admins_task.delay(text, org_id, modules=["admin", "purchases"])
    except Exception:  # noqa: BLE001
        logger.exception("notify_purchase_event: notify failed")
