from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class Batch(UUIDModel, TimestampedModel):
    """
    Сквозная партия (П-XXXX). Переживает межмодульные передачи,
    сохраняя doc_number и аккумулируя себестоимость.

    current_module / current_block / accumulated_cost_uzs — денормализация
    для hot-path фильтров и списков. Обновляется атомарно сервисами
    accept_transfer / append_cost (Phase 5).
    """

    class State(models.TextChoices):
        ACTIVE = "active", "Активна"
        IN_TRANSIT = "in_transit", "В пути"
        COMPLETED = "completed", "Завершена"
        REJECTED = "rejected", "Отклонена"
        REVIEW = "review", "На проверке"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="batches",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="batches",
    )
    unit = models.ForeignKey(
        "nomenclature.Unit",
        on_delete=models.PROTECT,
        related_name="+",
    )

    origin_module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="batches_originated",
    )
    current_module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="batches_current",
    )
    current_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_batches",
    )

    current_quantity = models.DecimalField(max_digits=18, decimal_places=3)
    initial_quantity = models.DecimalField(max_digits=18, decimal_places=3)
    accumulated_cost_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, default=0
    )

    state = models.CharField(
        max_length=16, choices=State.choices, default=State.ACTIVE, db_index=True
    )
    started_at = models.DateField()
    completed_at = models.DateField(null=True, blank=True)
    withdrawal_period_ends = models.DateField(null=True, blank=True, db_index=True)

    parent_batch = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="child_batches",
    )
    origin_purchase = models.ForeignKey(
        "purchases.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="originated_batches",
    )
    origin_counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
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
        ordering = ["-started_at", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "state"]),
            models.Index(fields=["current_module", "state"]),
            models.Index(fields=["organization", "-started_at"]),
            models.Index(fields=["parent_batch"]),
        ]
        verbose_name = "Партия"
        verbose_name_plural = "Партии"

    def __str__(self):
        return f"{self.doc_number} · {self.nomenclature.sku}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.parent_batch_id and self.parent_batch.organization_id != org_id:
            raise ValidationError(
                {"parent_batch": "Родительская партия из другой организации."}
            )
        if self.origin_purchase_id and self.origin_purchase.organization_id != org_id:
            raise ValidationError(
                {"origin_purchase": "Закуп из другой организации."}
            )
        if (
            self.origin_counterparty_id
            and self.origin_counterparty.organization_id != org_id
        ):
            raise ValidationError(
                {"origin_counterparty": "Контрагент из другой организации."}
            )
        if self.current_block_id:
            if self.current_block.organization_id != org_id:
                raise ValidationError(
                    {"current_block": "Блок из другой организации."}
                )
            if (
                self.current_module_id
                and self.current_block.module_id != self.current_module_id
            ):
                raise ValidationError(
                    {"current_block": "Блок не принадлежит текущему модулю партии."}
                )


class BatchCostEntry(UUIDModel, TimestampedModel):
    """
    Аналитическая проекция затрат по бакетам (FEED / VET / LABOR / ...).
    Не дублирует JournalEntry: один JE может породить 0 или 1 BatchCostEntry,
    BatchCostEntry может не иметь JE (feed task, transfer-in).
    """

    class Category(models.TextChoices):
        EGG_INHERITED = "egg_inherited", "Инкуб. яйцо (унаслед.)"
        FEED = "feed", "Комбикорм"
        VET = "vet", "Ветпрепараты"
        LABOR = "labor", "Зарплата"
        UTILITIES = "utilities", "Коммуналка"
        DEPRECIATION = "depreciation", "Амортизация"
        TRANSFER_IN = "transfer_in", "Переход от другого модуля"
        OTHER = "other", "Прочее"

    batch = models.ForeignKey(
        Batch, on_delete=models.PROTECT, related_name="cost_entries"
    )
    category = models.CharField(
        max_length=24, choices=Category.choices, db_index=True
    )
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(db_index=True)
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="batch_cost_entries",
    )

    source_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    source_object_id = models.UUIDField(null=True, blank=True)
    source = GenericForeignKey("source_content_type", "source_object_id")

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [
            models.Index(fields=["batch", "occurred_at"]),
            models.Index(fields=["batch", "category"]),
            models.Index(fields=["source_content_type", "source_object_id"]),
        ]
        verbose_name = "Затрата по партии"
        verbose_name_plural = "Затраты по партии"

    def __str__(self):
        return f"{self.batch.doc_number} · {self.get_category_display()} · {self.amount_uzs}"


class BatchChainStep(UUIDModel, TimestampedModel):
    """
    Денормализованная временная линия партии — по одной строке на каждый
    модуль, через который прошла партия. Используется страницей
    /traceability для быстрого рендера без N+1 aggregate.

    Sync-правило (Phase 5, сервис `accept_transfer`):
    при POSTED transfer-а:
      1. Закрыть текущий step (exited_at, quantity_out, accumulated_cost_at_exit).
      2. Создать новый step (sequence+1, module=to_module, entered_at=posted_at,
         quantity_in=transfer.quantity).
    Ручное редактирование запрещено (в admin inline read-only).
    """

    batch = models.ForeignKey(
        Batch, on_delete=models.CASCADE, related_name="chain_steps"
    )
    sequence = models.PositiveSmallIntegerField()
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="batch_chain_steps",
    )
    block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="batch_chain_steps",
    )
    entered_at = models.DateTimeField()
    exited_at = models.DateTimeField(null=True, blank=True)

    quantity_in = models.DecimalField(max_digits=18, decimal_places=3)
    quantity_out = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True
    )
    accumulated_cost_at_exit = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )

    transfer_in = models.ForeignKey(
        "transfers.InterModuleTransfer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="step_as_target",
    )
    transfer_out = models.ForeignKey(
        "transfers.InterModuleTransfer",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="step_as_source",
    )

    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["batch", "sequence"]
        unique_together = (("batch", "sequence"),)
        indexes = [
            models.Index(fields=["batch", "sequence"]),
            models.Index(fields=["module"]),
        ]
        verbose_name = "Шаг чейна партии"
        verbose_name_plural = "Шаги чейна партий"

    def __str__(self):
        return f"{self.batch.doc_number} · step {self.sequence} · {self.module.code}"
