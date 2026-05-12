from __future__ import annotations

import hmac
import logging
import secrets
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ..models import OtpCode, SmsMessage
from .sender import send_sms

logger = logging.getLogger(__name__)


class OtpError(Exception):
    """Базовая ошибка OTP-сервиса. У всех наследников есть .code для API."""

    code = "otp_error"
    status = 400


class OtpResendTooSoon(OtpError):
    code = "resend_too_soon"
    status = 429

    def __init__(self, retry_after: int):
        super().__init__("Запросить новый код можно позже.")
        self.retry_after = retry_after


class OtpNotFound(OtpError):
    code = "otp_not_found"
    status = 400


class OtpExpired(OtpError):
    code = "otp_expired"
    status = 400


class OtpTooManyAttempts(OtpError):
    code = "too_many_attempts"
    status = 429


class OtpInvalid(OtpError):
    code = "invalid_code"
    status = 400


@dataclass(frozen=True)
class RequestResult:
    otp_id: str
    expires_at: object
    resend_available_at: object
    message_id: str


# ── helpers ────────────────────────────────────────────────────────────────

def _hash_code(phone: str, purpose: str, code: str) -> str:
    """
    HMAC-SHA256(secret, phone|purpose|code). Привязываем хеш к телефону+
    purpose, чтобы код, утёкший вместе с дампом БД, нельзя было применить
    к чужой записи через подбор столкновений.
    """
    secret = settings.SECRET_KEY.encode("utf-8")
    payload = f"{phone}|{purpose}|{code}".encode("utf-8")
    return hmac.new(secret, payload, sha256).hexdigest()


def _generate_code(length: int) -> str:
    # secrets.randbelow гарантирует криптостойкий выбор без модульного смещения.
    upper = 10 ** length
    return str(secrets.randbelow(upper)).zfill(length)


def _format_message(code: str, template: str | None) -> str:
    template = template or getattr(
        settings,
        "OTP_MESSAGE_TEMPLATE",
        "Bu Eskiz dan test",  # дефолт совместим с тестовым sender 4546
    )
    if "{code}" in template:
        return template.format(code=code)
    return template


# ── public API ─────────────────────────────────────────────────────────────

def request_otp(
    *,
    phone: str,
    purpose: str,
    requested_ip: str | None = None,
    message_template: str | None = None,
) -> RequestResult:
    """
    Создаёт новый код и шлёт SMS. Старые непогашенные коды для этой
    пары (phone, purpose) принудительно помечаются использованными,
    чтобы исключить параллельные валидные коды.

    Защищает от частых повторов: между запросами должен пройти
    OTP_RESEND_INTERVAL_SECONDS. Если SMS-провайдер падает — запись
    в БД не остаётся (transaction.atomic + send_sms внутри транзакции).
    """
    ttl = int(getattr(settings, "OTP_TTL_SECONDS", 300))
    resend_interval = int(getattr(settings, "OTP_RESEND_INTERVAL_SECONDS", 60))
    max_attempts = int(getattr(settings, "OTP_MAX_ATTEMPTS", 5))
    code_length = int(getattr(settings, "OTP_CODE_LENGTH", 6))

    now = timezone.now()
    resend_threshold = now - timedelta(seconds=resend_interval)

    recent = (
        OtpCode.objects
        .filter(phone=phone, purpose=purpose, created_at__gte=resend_threshold)
        .order_by("-created_at")
        .first()
    )
    if recent is not None:
        retry_after = max(
            1,
            int((recent.created_at + timedelta(seconds=resend_interval) - now)
                .total_seconds()),
        )
        raise OtpResendTooSoon(retry_after=retry_after)

    code = _generate_code(code_length)
    code_hash = _hash_code(phone, purpose, code)

    with transaction.atomic():
        # Гасим все ещё-не-использованные коды для (phone, purpose),
        # чтобы был всегда максимум один валидный код.
        (
            OtpCode.objects
            .filter(phone=phone, purpose=purpose, used_at__isnull=True)
            .update(used_at=now)
        )
        otp = OtpCode.objects.create(
            phone=phone,
            purpose=purpose,
            code_hash=code_hash,
            max_attempts=max_attempts,
            expires_at=now + timedelta(seconds=ttl),
            requested_ip=requested_ip,
        )
        message = _format_message(code, message_template)
        sms = send_sms(
            phone=phone,
            message=message,
            source=SmsMessage.Source.OTP,
            purpose=purpose,
        )

    return RequestResult(
        otp_id=str(otp.id),
        expires_at=otp.expires_at,
        resend_available_at=otp.created_at + timedelta(seconds=resend_interval),
        message_id=sms.provider_message_id or "",
    )


def verify_otp(*, phone: str, purpose: str, code: str) -> OtpCode:
    """
    Проверяет код. На каждую неуспешную попытку инкрементит счётчик;
    при превышении лимита запись помечается использованной — повторно
    проверить нельзя, нужно запросить новый.
    """
    otp = (
        OtpCode.objects
        .filter(phone=phone, purpose=purpose, used_at__isnull=True)
        .order_by("-created_at")
        .first()
    )
    if otp is None:
        raise OtpNotFound("Код не запрашивался или уже использован.")

    now = timezone.now()
    if otp.expires_at <= now:
        otp.used_at = now
        otp.save(update_fields=["used_at", "updated_at"])
        raise OtpExpired("Срок действия кода истёк.")

    if otp.attempts >= otp.max_attempts:
        otp.used_at = now
        otp.save(update_fields=["used_at", "updated_at"])
        raise OtpTooManyAttempts("Превышено число попыток. Запросите новый код.")

    expected = _hash_code(phone, purpose, code)
    if not hmac.compare_digest(expected, otp.code_hash):
        otp.attempts += 1
        update_fields = ["attempts", "updated_at"]
        if otp.attempts >= otp.max_attempts:
            otp.used_at = now
            update_fields.append("used_at")
        otp.save(update_fields=update_fields)
        raise OtpInvalid("Неверный код.")

    otp.used_at = now
    otp.save(update_fields=["used_at", "updated_at"])
    return otp
