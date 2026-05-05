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

logger = logging.getLogger(__name__)


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

    # 2 + 3. Сотрудники: общий fmt_payment_posted в admin (>=r) и в
    # source-модуль (>=admin). Module-определение:
    #   - direction=in  → 'sales'   (это наш incoming, админ продаж/owner)
    #   - direction=out → 'purchases' (наша исходящая закупочная оплата)
    text_staff = fmt.fmt_payment_posted(payment)
    if payment.direction == "in":
        primary_module = "sales"
    else:
        primary_module = "purchases"

    try:
        # Org-wide admin (модуль 'admin' = global owner channel).
        notify_admins_task.delay(text_staff, org_id, "admin")
    except Exception:  # noqa: BLE001
        logger.exception("notify_payment_event: admin notify failed")

    try:
        # Head модуля (level=admin) + рядовые менеджеры (level>=r).
        # В одном вызове — все с >=r получат, head всё равно входит.
        # Если хочется ТОЛЬКО head — поднять min_level='admin'.
        notify_admins_task.delay(text_staff, org_id, primary_module)
    except Exception:  # noqa: BLE001
        logger.exception("notify_payment_event: module notify failed")


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

    # 2. Админы sales — общая сводка
    try:
        notify_admins_task.delay(fmt.fmt_sale_confirmed(order), org_id, "sales")
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
    """Проведённый закуп → админам организации + head'у purchases."""
    from .. import notifications as fmt
    from ..tasks import notify_admins_task

    org_id = str(order.organization_id)
    text = fmt.fmt_purchase_confirmed(order)
    for module_code in ("admin", "purchases"):
        try:
            notify_admins_task.delay(text, org_id, module_code)
        except Exception:  # noqa: BLE001
            logger.exception(
                "notify_purchase_event: module=%s notify failed", module_code,
            )
