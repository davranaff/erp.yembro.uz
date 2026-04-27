from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class DemoLead(UUIDModel, TimestampedModel):
    name = models.CharField(max_length=200, verbose_name="Имя")
    contact = models.CharField(max_length=200, verbose_name="Телефон / Email")
    company = models.CharField(max_length=200, blank=True, verbose_name="Компания")
    notified = models.BooleanField(default=False, verbose_name="Уведомление отправлено")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Заявка на демо"
        verbose_name_plural = "Заявки на демо"

    def __str__(self) -> str:
        return f"{self.name} / {self.contact}"
