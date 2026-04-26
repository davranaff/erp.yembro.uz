from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class Module(UUIDModel, TimestampedModel):
    class Kind(models.TextChoices):
        CORE = "core", "Ядро"
        MATOCHNIK = "matochnik", "Маточник"
        INCUBATION = "incubation", "Инкубация"
        FEEDLOT = "feedlot", "Фабрика откорма"
        SLAUGHTER = "slaughter", "Убойня"
        FEED = "feed", "Корма"
        VET = "vet", "Вет. аптека"
        STOCK = "stock", "Склад и движения"
        LEDGER = "ledger", "Проводки"
        REPORTS = "reports", "Отчёты"
        PURCHASES = "purchases", "Закупки"
        SALES = "sales", "Продажи"
        ADMIN = "admin", "Администрирование"

    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=128)
    kind = models.CharField(max_length=32, choices=Kind.choices, unique=True)
    icon = models.CharField(max_length=64, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "code"]
        verbose_name = "Модуль"
        verbose_name_plural = "Модули"

    def __str__(self):
        return f"{self.code} · {self.name}"


class OrganizationModule(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="enabled_modules",
    )
    module = models.ForeignKey(
        Module,
        on_delete=models.PROTECT,
        related_name="org_activations",
    )
    is_enabled = models.BooleanField(default=True)
    enabled_at = models.DateTimeField(null=True, blank=True)
    settings_json = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = (("organization", "module"),)
        indexes = [models.Index(fields=["organization", "is_enabled"])]
        verbose_name = "Модуль организации"
        verbose_name_plural = "Модули организаций"

    def __str__(self):
        return f"{self.organization.code} · {self.module.code}"
