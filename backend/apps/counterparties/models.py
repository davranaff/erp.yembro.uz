from django.db import models

from apps.common.models import TimestampedModel, UUIDModel

from .validators import validate_inn


class Counterparty(UUIDModel, TimestampedModel):
    class Kind(models.TextChoices):
        SUPPLIER = "supplier", "Поставщик"
        BUYER = "buyer", "Покупатель"
        OTHER = "other", "Прочее"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="counterparties",
    )
    code = models.CharField(max_length=32)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    name = models.CharField(max_length=255)
    inn = models.CharField(max_length=14, blank=True, validators=[validate_inn])
    specialization = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=32, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    balance_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        indexes = [
            models.Index(fields=["organization", "kind"]),
            models.Index(fields=["name"]),
        ]
        verbose_name = "Контрагент"
        verbose_name_plural = "Контрагенты"

    def __str__(self):
        return f"{self.code} · {self.name}"
