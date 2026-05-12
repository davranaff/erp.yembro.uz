from __future__ import annotations

import logging

from django.conf import settings

from .eskiz import get_eskiz_client

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> str:
    """
    Универсальная точка отправки SMS.

    При OTP_DEV_PRINT=True (по умолчанию в DEBUG) ничего не уходит наружу
    и код пишется в лог — удобно для локальной разработки без реальных
    SMS-расходов. В проде всегда False, используется Eskiz.

    Возвращает идентификатор отправленного сообщения (или 'dev-stub' в dev).
    """
    if getattr(settings, "OTP_DEV_PRINT", False):
        logger.warning("[OTP-DEV] SMS to %s: %s", phone, message)
        return "dev-stub"

    client = get_eskiz_client()
    return client.send_sms(phone, message)
