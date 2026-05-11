from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


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
