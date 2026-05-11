"""
Celery-задачи каталога:
- notify_contact_request_task — уведомление в Telegram о новой заявке
- revalidate_next_task — стучится в Next.js /api/revalidate с тегами,
  чтобы ISR-страницы перевыпустили HTML после правки контента.
"""
from __future__ import annotations

import logging
from typing import Iterable

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(name="apps.catalog.notify_contact_request_task")
def notify_contact_request_task(req_id: str) -> dict:
    from django.conf import settings

    from apps.tgbot.bot import send_message

    from .models import ContactRequest

    try:
        req = ContactRequest.objects.get(id=req_id)
    except ContactRequest.DoesNotExist:
        return {"error": "request_not_found"}

    chat_ids_raw = getattr(settings, "CATALOG_NOTIFY_CHAT_IDS", "") or getattr(
        settings, "DEMO_NOTIFY_CHAT_IDS", "",
    )
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
    if not chat_ids:
        logger.warning("notify_contact_request: no chat_ids configured")
        return {"sent": 0}

    tz = req.created_at.astimezone()
    text = (
        f"📨 <b>Новая заявка с каталога</b>\n\n"
        f"👤 {req.name}\n"
        f"📞 {req.contact}\n"
        f"🏢 {req.company or '—'}\n"
        f"🌐 lang={req.source_lang}  url={req.source_url or '—'}\n"
        f"💬 {req.message[:400] if req.message else '—'}\n"
        f"🕐 {tz:%d.%m.%Y %H:%M}"
    )

    sent = 0
    for chat_id in chat_ids:
        if send_message(int(chat_id), text):
            sent += 1
    req.notified = sent > 0
    req.save(update_fields=["notified"])
    return {"sent": sent}


@shared_task(name="apps.catalog.revalidate_next_task")
def revalidate_next_task(tags: Iterable[str]) -> dict:
    """POST на Next.js /api/revalidate чтобы инвалидировать ISR-кэш."""
    import requests
    from django.conf import settings

    base = getattr(settings, "CATALOG_FRONTEND_URL", "")
    secret = getattr(settings, "CATALOG_REVALIDATE_SECRET", "")
    if not base or not secret:
        return {"skipped": "not_configured"}

    payload = {"secret": secret, "tags": list(tags)}
    try:
        r = requests.post(
            f"{base.rstrip('/')}/api/revalidate",
            json=payload,
            timeout=10,
        )
        return {"status": r.status_code, "tags": payload["tags"]}
    except Exception as exc:
        logger.warning("revalidate_next_task failed: %s", exc)
        return {"error": str(exc)}
