from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.tgbot.notify_admins_task")
def notify_admins_task(text: str, organization_id: str) -> dict:
    """Рассылает text всем активным TgLink (admin) для org."""
    from .bot import send_message
    from .models import TgLink

    links = TgLink.objects.filter(
        organization_id=organization_id,
        is_active=True,
        user__isnull=False,
    )
    sent = 0
    for link in links:
        if send_message(link.chat_id, text):
            sent += 1
    logger.info("notify_admins_task: sent=%d org=%s", sent, organization_id)
    return {"sent": sent}


@shared_task(name="apps.tgbot.send_debt_reminder_task")
def send_debt_reminder_task(sale_order_id: str) -> dict:
    """Отправляет напоминание о долге по конкретному SaleOrder."""
    from apps.sales.models import SaleOrder

    from .bot import send_message
    from .models import TgLink
    from .notifications import fmt_debt_reminder_uz

    try:
        order = SaleOrder.objects.select_related("counterparty", "organization").get(
            id=sale_order_id
        )
    except SaleOrder.DoesNotExist:
        return {"error": "sale_order_not_found"}

    link = TgLink.objects.filter(
        organization=order.organization,
        counterparty=order.counterparty,
        is_active=True,
        counterparty__isnull=False,
    ).first()

    if not link:
        return {"error": "no_tg_link", "order": sale_order_id}

    text = fmt_debt_reminder_uz(order, order.counterparty)
    ok = send_message(link.chat_id, text)
    return {"sent": ok, "chat_id": link.chat_id}


@shared_task(name="apps.tgbot.debt_reminder_daily_task")
def debt_reminder_daily_task() -> dict:
    """Celery Beat: каждый день в 09:00 — напоминания всем должникам."""
    from apps.sales.models import SaleOrder

    overdue = SaleOrder.objects.filter(
        status=SaleOrder.Status.CONFIRMED,
    ).exclude(payment_status=SaleOrder.PaymentStatus.PAID)

    count = 0
    for order in overdue:
        send_debt_reminder_task.delay(str(order.id))
        count += 1

    logger.info("debt_reminder_daily_task: queued=%d", count)
    return {"queued": count}


@shared_task(name="apps.tgbot.handle_tg_update_task")
def handle_tg_update_task(update: dict) -> None:
    """Обрабатывает входящий Telegram update."""
    from .commands import dispatch
    try:
        dispatch(update)
    except Exception as exc:
        logger.error("handle_tg_update_task error: %s", exc, exc_info=True)
