from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_message(chat_id: int, text: str, parse_mode: str = "HTML") -> bool:
    token = getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skip send_message")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": parse_mode},
            timeout=10,
        )
        if not resp.ok:
            logger.warning("Telegram sendMessage failed: %s %s", resp.status_code, resp.text[:200])
        return resp.ok
    except requests.RequestException as exc:
        logger.error("Telegram sendMessage error: %s", exc)
        return False
