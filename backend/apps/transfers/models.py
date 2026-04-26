from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class InterModuleTransfer(UUIDModel, TimestampedModel):
    """
    Межмодульная передача партии (ММ-XXXX).

    Валидные переходы state (FSM enforcement — Phase 5):
        DRAFT → AWAITING_ACCEPTANCE → UNDER_REVIEW → POSTED
                         ↘                ↘
                          ↘                → CANCELLED
                           → POSTED
        DRAFT / AWAITING_ACCEPTANCE / UNDER_REVIEW → CANCELLED
        POSTED — иммутабельно (reversal только через компенсирующую запись)

    При POSTED сервис создаёт пару JournalEntry (Dr 79.01 Cr source / Dr dest Cr 79.01),
    пару StockMovement (outgoing/incoming), закрывает текущий BatchChainStep,
    создаёт новый BatchChainStep для нового модуля.
    """

    class State(models.TextChoices):
        DRAFT = "draft", "Черновик"
        AWAITING_ACCEPTANCE = "awaiting_acceptance", "Ожидает приёма"
        UNDER_REVIEW = "under_review", "На проверке"
        POSTED = "posted", "Проведён"
        CANCELLED = "cancelled", "Отменён"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="inter_module_transfers",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    transfer_date = models.DateTimeField(db_index=True)

    from_module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )
    from_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )
    from_warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_out",
    )
    to_warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="transfers_in",
    )

    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="inter_module_transfers",
    )
    unit = models.ForeignKey(
        "nomenclature.Unit",
        on_delete=models.PROTECT,
        related_name="+",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    cost_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inter_module_transfers",
    )
    feed_batch = models.ForeignKey(
        "feed.FeedBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="inter_module_transfers",
    )

    state = models.CharField(
        max_length=24, choices=State.choices, default=State.DRAFT, db_index=True
    )
    review_reason = models.CharField(max_length=255, blank=True)

    journal_sender = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    journal_receiver = models.ForeignKey(
        "accounting.JournalEntry",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    stock_outgoing = models.ForeignKey(
        "warehouses.StockMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    stock_incoming = models.ForeignKey(
        "warehouses.StockMovement",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    accepted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-transfer_date", "-created_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-transfer_date"]),
            models.Index(fields=["state"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["feed_batch"]),
            models.Index(fields=["to_module", "state"]),
            models.Index(fields=["from_module", "state"]),
        ]
        verbose_name = "Межмодульная передача"
        verbose_name_plural = "Межмодульные передачи"

    def __str__(self):
        return f"{self.doc_number} · {self.from_module.code}→{self.to_module.code}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return

        if self.from_module_id and self.to_module_id:
            if self.from_module_id == self.to_module_id:
                raise ValidationError(
                    "Передача возможна только между разными модулями."
                )

        # XOR: ровно один из batch / feed_batch должен быть задан
        has_batch = bool(self.batch_id)
        has_feed = bool(self.feed_batch_id)
        if has_batch and has_feed:
            raise ValidationError(
                "Передача связывается либо с птице-партией, либо с партией корма — не с обеими."
            )
        if not has_batch and not has_feed:
            raise ValidationError(
                "Нужно указать либо партию (batch), либо партию корма (feed_batch)."
            )

        if self.batch_id and self.batch.organization_id != org_id:
            raise ValidationError({"batch": "Партия из другой организации."})

        if self.feed_batch_id:
            if self.feed_batch.organization_id != org_id:
                raise ValidationError(
                    {"feed_batch": "Партия корма из другой организации."}
                )
            if (
                self.from_module_id
                and self.feed_batch.module_id != self.from_module_id
            ):
                raise ValidationError(
                    {"from_module": "Партия корма принадлежит другому модулю."}
                )

        self._validate_block_module("from_block", "from_module", org_id)
        self._validate_block_module("to_block", "to_module", org_id)
        self._validate_warehouse_module("from_warehouse", "from_module", org_id)
        self._validate_warehouse_module("to_warehouse", "to_module", org_id)

        for attr in ("journal_sender", "journal_receiver", "stock_outgoing", "stock_incoming"):
            obj = getattr(self, attr)
            if obj and obj.organization_id != org_id:
                raise ValidationError({attr: "Связанный документ из другой организации."})

    def _validate_block_module(self, block_attr, module_attr, org_id):
        block = getattr(self, block_attr)
        if not block:
            return
        if block.organization_id != org_id:
            raise ValidationError({block_attr: "Блок из другой организации."})
        module_id = getattr(self, f"{module_attr}_id")
        if module_id and block.module_id != module_id:
            raise ValidationError({block_attr: "Блок не принадлежит указанному модулю."})

    def _validate_warehouse_module(self, warehouse_attr, module_attr, org_id):
        warehouse = getattr(self, warehouse_attr)
        if not warehouse:
            return
        if warehouse.organization_id != org_id:
            raise ValidationError({warehouse_attr: "Склад из другой организации."})
        module_id = getattr(self, f"{module_attr}_id")
        if module_id and warehouse.module_id != module_id:
            raise ValidationError({warehouse_attr: "Склад не принадлежит указанному модулю."})
