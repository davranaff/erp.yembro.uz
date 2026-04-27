from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class PurchaseOrder(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        CONFIRMED = "confirmed", "Проведён"
        PAID = "paid", "Оплачен"
        CANCELLED = "cancelled", "Отменён"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Не оплачен"
        PARTIAL = "partial", "Частично оплачен"
        PAID = "paid", "Оплачен"
        OVERPAID = "overpaid", "Переплата"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    date = models.DateField(db_index=True)

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT
    )

    currency = models.ForeignKey(
        "currency.Currency",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="purchase_orders",
    )
    exchange_rate = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True
    )
    exchange_rate_source = models.ForeignKey(
        "currency.ExchangeRate",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referenced_by_purchases",
    )
    # Если задан до confirm — confirm_purchase возьмёт этот курс вместо
    # cbu.uz. После confirm копируется в exchange_rate (snapshot) и
    # exchange_rate_source остаётся NULL (источник — пользователь, не CBU).
    exchange_rate_override = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text=(
            "Ручной курс, переопределяющий CBU. Заполняется в DRAFT, "
            "применяется при confirm. Если NULL — берётся курс ЦБ Узбекистана."
        ),
    )
    amount_foreign = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    paid_amount_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )
    payment_status = models.CharField(
        max_length=16,
        choices=PaymentStatus.choices,
        default=PaymentStatus.UNPAID,
        db_index=True,
    )

    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="originating_purchases",
    )

    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-date", "-created_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["counterparty"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["payment_status"]),
        ]
        verbose_name = "Закуп"
        verbose_name_plural = "Закупы"

    def __str__(self):
        return f"{self.doc_number} · {self.date}"

    def clean(self):
        super().clean()
        if (
            self.organization_id
            and self.batch_id
            and self.batch.organization_id != self.organization_id
        ):
            raise ValidationError({"batch": "Партия из другой организации."})


class PurchaseItem(UUIDModel, TimestampedModel):
    order = models.ForeignKey(
        PurchaseOrder, on_delete=models.CASCADE, related_name="items"
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="purchase_items",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    received_qty = models.DecimalField(
        max_digits=18, decimal_places=3, default=0,
        help_text="Фактически принятое количество (частичная поставка).",
    )
    unit_price = models.DecimalField(max_digits=18, decimal_places=2)
    line_total_foreign = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    line_total_uzs = models.DecimalField(max_digits=18, decimal_places=2, default=0)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Строка закупа"
        verbose_name_plural = "Строки закупа"

    def __str__(self):
        return f"{self.nomenclature} × {self.quantity}"
