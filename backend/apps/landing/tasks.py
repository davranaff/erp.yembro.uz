from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.landing.notify_demo_lead_task")
def notify_demo_lead_task(lead_id: str) -> dict:
    from django.conf import settings

    from apps.tgbot.bot import send_message

    from .models import DemoLead

    try:
        lead = DemoLead.objects.get(id=lead_id)
    except DemoLead.DoesNotExist:
        return {"error": "lead_not_found"}

    chat_ids_raw = getattr(settings, "DEMO_NOTIFY_CHAT_IDS", "")
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]

    if not chat_ids:
        logger.warning("notify_demo_lead_task: DEMO_NOTIFY_CHAT_IDS not configured")
        return {"sent": 0}

    tz = lead.created_at.astimezone()
    text = (
        f"📋 <b>Новая заявка на демо</b>\n\n"
        f"👤 {lead.name}\n"
        f"📞 {lead.contact}\n"
        f"🏢 {lead.company or '—'}\n"
        f"🕐 {tz:%d.%m.%Y %H:%M}"
    )

    sent = 0
    for chat_id in chat_ids:
        if send_message(int(chat_id), text):
            sent += 1

    lead.notified = sent > 0
    lead.save(update_fields=["notified"])

    logger.info("notify_demo_lead_task: sent=%d lead=%s", sent, lead_id)
    return {"sent": sent}
