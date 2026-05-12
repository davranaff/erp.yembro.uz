"""
Celery-tasks для SMS:
  - poll_pending_sms_status: подтягивает статус у SMS, которые ушли
    провайдеру, но webhook ещё не прилетел в течение N минут.
  - check_eskiz_balance: алертит в Telegram, когда баланс упал
    ниже порога ESKIZ_BALANCE_ALERT_THRESHOLD_UZS.

Beat-расписание прописано в config/settings.py → CELERY_BEAT_SCHEDULE.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .models import SmsMessage
from .services.eskiz import EskizConfigError, EskizError, get_eskiz_client

logger = logging.getLogger(__name__)


@shared_task(name="apps.otp.poll_pending_sms_status")
def poll_pending_sms_status_task(*, max_age_minutes: int = 30) -> dict:
    """
    Запрос статусов у Eskiz для SMS, ушедших > 5 минут назад, но ещё не
    DELIVERED/FAILED по нашим данным. Защита: не трогаем записи старше
    max_age_minutes (по ним webhook уже точно не придёт, лезть бесполезно).
    """
    try:
        client = get_eskiz_client()
    except EskizConfigError as exc:
        logger.warning("poll_pending_sms_status: %s", exc)
        return {"checked": 0, "skipped_no_config": True}

    now = timezone.now()
    qs = SmsMessage.objects.filter(
        status=SmsMessage.Status.SENT,
        sent_at__lte=now - timedelta(minutes=5),
        sent_at__gte=now - timedelta(minutes=max_age_minutes),
    ).exclude(provider_message_id="")

    checked = 0
    updated = 0
    for sms in qs.iterator():
        try:
            data = client.get_status(sms.provider_message_id)
        except EskizError as exc:
            logger.warning(
                "poll_pending_sms_status: %s — %s", sms.provider_message_id, exc,
            )
            continue
        checked += 1
        status_value = (data.get("status") or "").upper()
        if not status_value:
            continue
        fields = ["updated_at"]
        if status_value == "DELIVERED" or status_value == "DELIVRD":
            sms.status = SmsMessage.Status.DELIVERED
            sms.delivered_at = now
            fields += ["status", "delivered_at"]
        elif status_value in ("EXPIRED", "REJECTED", "UNDELIV", "FAILED"):
            sms.status = SmsMessage.Status.FAILED
            sms.failed_at = now
            sms.error_msg = f"poll: {status_value}"
            fields += ["status", "failed_at", "error_msg"]
        # цена приходит как `price` (UZS)
        price = data.get("price")
        if price is not None:
            try:
                sms.cost_uzs = Decimal(str(price))
                fields.append("cost_uzs")
            except (ValueError, ArithmeticError):
                pass
        if len(fields) > 1:
            sms.save(update_fields=fields)
            updated += 1
    return {"checked": checked, "updated": updated}


@shared_task(name="apps.otp.check_eskiz_balance")
def check_eskiz_balance_task() -> dict:
    """
    Ежечасный чек баланса. Если меньше порога → TG-уведомление.
    Чтобы не спамить, шлём не чаще раза в день.
    """
    try:
        client = get_eskiz_client()
    except EskizConfigError as exc:
        logger.warning("check_eskiz_balance: %s", exc)
        return {"skipped_no_config": True}

    try:
        balance = client.get_balance()
    except EskizError as exc:
        logger.exception("check_eskiz_balance: %s", exc)
        return {"error": str(exc)[:200]}

    threshold = int(getattr(settings, "ESKIZ_BALANCE_ALERT_THRESHOLD_UZS", 50_000))
    result = {"balance": balance, "threshold": threshold}
    if balance >= threshold:
        return result

    # Anti-spam: не дёргаем TG чаще 1 раза в сутки.
    from django.core.cache import cache
    flag_key = "sms:eskiz:balance_alert_sent"
    if cache.get(flag_key):
        result["alert_skipped"] = "already_sent_today"
        return result

    # TG-алерт через существующий tgbot-инфраструктуру.
    try:
        from apps.tgbot.bot import send_message
    except Exception:  # pragma: no cover
        logger.warning("check_eskiz_balance: tgbot.send_message недоступен")
        result["alert_failed"] = "tgbot_unavailable"
        return result

    chat_ids_raw = getattr(settings, "DEMO_NOTIFY_CHAT_IDS", "") or ""
    chat_ids = [c.strip() for c in chat_ids_raw.split(",") if c.strip()]
    if not chat_ids:
        result["alert_skipped"] = "no_chat_ids"
        return result

    text = (
        f"⚠️ <b>Eskiz SMS — низкий баланс</b>\n\n"
        f"Текущий баланс: <b>{balance:,} UZS</b>\n"
        f"Порог алерта: {threshold:,} UZS\n\n"
        f"Пополните: <a href=\"https://my.eskiz.uz/billing\">my.eskiz.uz/billing</a>"
    )
    sent = 0
    for cid in chat_ids:
        try:
            if send_message(int(cid), text):
                sent += 1
        except Exception:  # pragma: no cover
            pass
    cache.set(flag_key, True, 60 * 60 * 24)
    result["alert_sent_to"] = sent
    return result
