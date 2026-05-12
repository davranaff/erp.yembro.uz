from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.utils import timezone

from ..models import SmsMessage
from .eskiz import EskizError, get_eskiz_client

logger = logging.getLogger(__name__)


def send_sms(
    *,
    phone: str,
    message: str,
    source: str = SmsMessage.Source.NOTIFY,
    purpose: str = "",
    created_by=None,
) -> SmsMessage:
    """
    Универсальная точка отправки SMS с журналом.

    Алгоритм:
      1. Создаём запись `SmsMessage` со status=QUEUED.
      2. При OTP_DEV_PRINT=True — пишем код в лог, помечаем DELIVERED (для dev).
      3. Иначе вызываем Eskiz; на успехе → SENT + provider_message_id;
         на ошибке → FAILED + error_msg.

    Запись всегда сохраняется (даже при сбое провайдера) — это даёт нам
    аудит, по которому видно «попытки отправки» и «реально доставленные».
    """
    sms = SmsMessage.objects.create(
        phone=phone,
        message=message,
        source=source,
        purpose=purpose,
        status=SmsMessage.Status.QUEUED,
        created_by=created_by,
    )

    if getattr(settings, "OTP_DEV_PRINT", False):
        logger.warning("[OTP-DEV] SMS to %s: %s", phone, message)
        sms.status = SmsMessage.Status.DELIVERED
        sms.sent_at = timezone.now()
        sms.delivered_at = timezone.now()
        sms.provider_message_id = "dev-stub"
        sms.save(update_fields=[
            "status", "sent_at", "delivered_at", "provider_message_id", "updated_at",
        ])
        return sms

    client = get_eskiz_client()
    try:
        message_id = client.send_sms(phone, message)
    except EskizError as exc:
        logger.exception("send_sms: Eskiz отказал — %s", exc)
        sms.status = SmsMessage.Status.FAILED
        sms.failed_at = timezone.now()
        sms.error_msg = str(exc)[:1000]
        sms.save(update_fields=[
            "status", "failed_at", "error_msg", "updated_at",
        ])
        raise

    sms.status = SmsMessage.Status.SENT
    sms.sent_at = timezone.now()
    sms.provider_message_id = message_id
    sms.save(update_fields=[
        "status", "sent_at", "provider_message_id", "updated_at",
    ])
    return sms


def update_status_from_callback(
    *,
    provider_message_id: str,
    status: str,
    status_date: Optional[str] = None,
    raw_payload: Optional[dict] = None,
) -> Optional[SmsMessage]:
    """
    Обновляет SmsMessage по callback'у от Eskiz. Идемпотентно.

    Eskiz присылает status вроде 'DELIVRD' / 'EXPIRED' / 'REJECTED' / 'UNDELIV'.
    Только 'DELIVRD' трактуется как успешная доставка, всё остальное — failure.
    """
    sms = SmsMessage.objects.filter(
        provider_message_id=provider_message_id,
    ).order_by("-created_at").first()
    if not sms:
        logger.warning(
            "sms callback: provider_message_id %s не найден — игнорируем",
            provider_message_id,
        )
        return None

    now = timezone.now()
    delivered = status.upper() == "DELIVRD"
    fields = ["provider_response", "updated_at"]
    if raw_payload is not None:
        sms.provider_response = str(raw_payload)[:5000]

    if delivered:
        if sms.status != SmsMessage.Status.DELIVERED:
            sms.status = SmsMessage.Status.DELIVERED
            sms.delivered_at = now
            fields += ["status", "delivered_at"]
    else:
        if sms.status != SmsMessage.Status.FAILED:
            sms.status = SmsMessage.Status.FAILED
            sms.failed_at = now
            sms.error_msg = (sms.error_msg or "") + f"\ncallback: {status}"
            fields += ["status", "failed_at", "error_msg"]

    sms.save(update_fields=fields)
    return sms
