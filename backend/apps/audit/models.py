from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class AuditLog(UUIDModel, TimestampedModel):
    class Action(models.TextChoices):
        CREATE = "create", "Создание"
        UPDATE = "update", "Изменение"
        DELETE = "delete", "Удаление"
        POST = "post", "Проведение"
        UNPOST = "unpost", "Отмена проведения"
        LOGIN = "login", "Вход"
        LOGOUT = "logout", "Выход"
        EXPORT = "export", "Экспорт"
        IMPORT = "import", "Импорт"
        PERMISSION_CHANGE = "permission_change", "Изменение прав"
        OTHER = "other", "Прочее"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="audit_logs",
    )
    module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_logs",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    action_verb = models.CharField(max_length=64, blank=True)

    entity_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    entity_object_id = models.UUIDField(null=True, blank=True)
    entity = GenericForeignKey("entity_content_type", "entity_object_id")
    entity_repr = models.CharField(max_length=255, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    diff = models.JSONField(null=True, blank=True)
    occurred_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["organization", "-occurred_at"]),
            models.Index(fields=["entity_content_type", "entity_object_id"]),
            models.Index(fields=["actor", "-occurred_at"]),
            models.Index(fields=["action"]),
        ]
        verbose_name = "Запись аудита"
        verbose_name_plural = "Записи аудита"

    def __str__(self):
        return f"{self.occurred_at:%Y-%m-%d %H:%M} · {self.action} · {self.entity_repr}"
