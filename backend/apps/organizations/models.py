from django.conf import settings
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel
from apps.counterparties.validators import validate_inn


class Organization(UUIDModel, TimestampedModel):
    class Direction(models.TextChoices):
        BROILER = "broiler", "Бройлер"
        EGG = "egg", "Яичное"
        MIXED = "mixed", "Смешанное"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255)
    legal_name = models.CharField(max_length=255, blank=True)
    inn = models.CharField(max_length=14, blank=True, validators=[validate_inn])
    legal_address = models.TextField(blank=True)
    direction = models.CharField(max_length=16, choices=Direction.choices)
    accounting_currency = models.ForeignKey(
        "currency.Currency",
        on_delete=models.PROTECT,
        related_name="+",
    )
    timezone = models.CharField(max_length=64, default="Asia/Tashkent")
    logo = models.ImageField(upload_to="org_logos/", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        indexes = [models.Index(fields=["is_active"])]
        verbose_name = "Организация"
        verbose_name_plural = "Организации"

    def __str__(self):
        return f"{self.code} · {self.name}"


class OrganizationMembership(UUIDModel, TimestampedModel):
    class WorkStatus(models.TextChoices):
        ACTIVE = "active", "Активен"
        VACATION = "vacation", "Отпуск"
        SICK_LEAVE = "sick_leave", "Больничный"
        TERMINATED = "terminated", "Уволен"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    is_active = models.BooleanField(default=True)
    position_title = models.CharField(max_length=128, blank=True)
    work_phone = models.CharField(max_length=32, blank=True)
    work_status = models.CharField(
        max_length=16,
        choices=WorkStatus.choices,
        default=WorkStatus.ACTIVE,
        db_index=True,
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (("user", "organization"),)
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "work_status"]),
        ]
        verbose_name = "Участник организации"
        verbose_name_plural = "Участники организаций"

    def __str__(self):
        return f"{self.user} @ {self.organization.code}"
