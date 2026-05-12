from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class SmsMessage(UUIDModel, TimestampedModel):
    """
    Журнал исходящих SMS. Любая отправка (OTP, уведомление, ручная) сначала
    создаёт запись со статусом `queued`, потом сервис вызывает Eskiz, пишет
    `provider_message_id` + `sent_at`. Webhook `/api/sms/callback/<secret>/`
    обновляет `delivered_at` или `failed_at`. Celery-poller подтягивает
    статус для тех записей, по которым webhook не пришёл.

    Хранение текстов: для OTP-сообщений `message` хранит уже подставленный
    текст с кодом — это аудит, кому что ушло. Если требуется compliance —
    PII-чистка делается отдельной задачей.
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "В очереди"
        SENT = "sent", "Отправлено провайдеру"
        DELIVERED = "delivered", "Доставлено"
        FAILED = "failed", "Ошибка"

    class Source(models.TextChoices):
        OTP = "otp", "OTP-код"
        NOTIFY = "notify", "Уведомление"
        MANUAL = "manual", "Ручная отправка"

    phone = models.CharField(max_length=16, db_index=True)
    message = models.TextField()
    source = models.CharField(
        max_length=16, choices=Source.choices, default=Source.NOTIFY, db_index=True,
    )
    purpose = models.CharField(
        max_length=32, blank=True,
        help_text="Контекст: 'login', 'sale_ready', 'debt_reminder' и т.п.",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED, db_index=True,
    )

    provider_message_id = models.CharField(max_length=128, blank=True, db_index=True)
    provider_response = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_msg = models.TextField(blank=True)
    cost_uzs = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text="Стоимость по данным провайдера (price из status_by_id).",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_messages_created",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["source", "-created_at"]),
        ]
        verbose_name = "SMS-сообщение"
        verbose_name_plural = "SMS-сообщения"

    def __str__(self) -> str:
        return f"{self.phone} · {self.source} · {self.status}"


class OtpCode(UUIDModel, TimestampedModel):
    """
    Одноразовый код подтверждения, привязанный к телефону и назначению.

    Код в БД хранится только хешем (HMAC-SHA256 с DJANGO_SECRET_KEY) —
    при утечке дампа БД сами коды не восстановить. `purpose` — свободная
    строка, заданная клиентом: 'login', 'verify_phone', 'reset_password'
    и т.п., чтобы один и тот же телефон мог иметь параллельные коды
    под разные сценарии.
    """

    phone = models.CharField(max_length=16, db_index=True)
    purpose = models.CharField(max_length=32, db_index=True)
    code_hash = models.CharField(max_length=64)
    attempts = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    requested_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["phone", "purpose", "-created_at"]),
        ]
        verbose_name = "OTP-код"
        verbose_name_plural = "OTP-коды"

    def __str__(self) -> str:
        return f"{self.phone} · {self.purpose} · {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_used(self) -> bool:
        return self.used_at is not None
