from django.db import models
from django.utils import timezone

from apps.common.models import TimestampedModel, UUIDModel


class Currency(UUIDModel, TimestampedModel):
    code = models.CharField(max_length=3, unique=True)
    numeric_code = models.CharField(max_length=3, blank=True)
    name_ru = models.CharField(max_length=64)
    name_en = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "Валюта"
        verbose_name_plural = "Валюты"

    def __str__(self):
        return self.code


class ExchangeRate(UUIDModel, TimestampedModel):
    currency = models.ForeignKey(
        Currency, on_delete=models.PROTECT, related_name="rates"
    )
    date = models.DateField(db_index=True)
    rate = models.DecimalField(max_digits=18, decimal_places=6)
    nominal = models.PositiveIntegerField(default=1)
    source = models.CharField(max_length=32, default="cbu.uz")
    fetched_at = models.DateTimeField()

    class Meta:
        unique_together = ("currency", "date", "source")
        ordering = ["-date", "currency__code"]
        indexes = [
            models.Index(fields=["currency", "-date"]),
        ]
        verbose_name = "Курс валюты"
        verbose_name_plural = "Курсы валют"

    def __str__(self):
        return f"{self.currency.code} {self.date} = {self.rate}"


class IntegrationSyncLog(UUIDModel, TimestampedModel):
    """
    Журнал попыток синхронизации с внешними провайдерами (cbu.uz и др.).

    Запись создаётся каждый раз когда выполнена попытка sync — успешная
    или неуспешная. Используется админом для диагностики, когда курсы
    «застряли» на старой дате (Celery упал, провайдер недоступен и т.п.).

    Зачем не AuditLog: AuditLog требует organization (NOT NULL), а CBU sync
    глобальный системный процесс без org-контекста.
    """

    class Status(models.TextChoices):
        SUCCESS = "success", "Успех"
        FAILED = "failed", "Ошибка"

    provider = models.CharField(max_length=32, db_index=True, default="cbu.uz")
    status = models.CharField(
        max_length=16, choices=Status.choices, db_index=True
    )
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)
    triggered_by = models.CharField(
        max_length=128,
        blank=True,
        help_text="email юзера для ручного запуска или 'beat' для Celery.",
    )
    stats = models.JSONField(
        null=True,
        blank=True,
        help_text="Счётчики успешного sync (fetched/created/updated/...).",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["provider", "-occurred_at"]),
            models.Index(fields=["status", "-occurred_at"]),
        ]
        verbose_name = "Журнал интеграции"
        verbose_name_plural = "Журнал интеграций"

    def __str__(self):
        return f"{self.provider} {self.status} {self.occurred_at:%Y-%m-%d %H:%M}"
