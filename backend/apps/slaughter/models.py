from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel
from apps.warehouses.models import ProductionBlock


class SlaughterShift(UUIDModel, TimestampedModel):
    """Смена на линии убоя."""

    class Status(models.TextChoices):
        ACTIVE = "active", "В работе"
        CLOSED = "closed", "Закрыта"
        POSTED = "posted", "Проведена"
        CANCELLED = "cancelled", "Отменена"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="slaughter_shifts",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="slaughter_shifts",
    )
    line_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="slaughter_shifts",
    )
    source_batch = models.ForeignKey(
        "batches.Batch",
        on_delete=models.PROTECT,
        related_name="slaughter_shifts",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    shift_date = models.DateField(db_index=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField(null=True, blank=True)
    live_heads_received = models.PositiveIntegerField()
    live_weight_kg_total = models.DecimalField(max_digits=12, decimal_places=3)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    foreman = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="slaughter_shifts_led",
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
        ordering = ["-shift_date", "-start_time"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["line_block", "shift_date"]),
            models.Index(fields=["source_batch"]),
            models.Index(fields=["organization", "-shift_date"]),
        ]
        verbose_name = "Смена убоя"
        verbose_name_plural = "Смены убоя"

    def __str__(self):
        return f"{self.doc_number} · {self.shift_date} · {self.source_batch.doc_number}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.source_batch_id and self.source_batch.organization_id != org_id:
            raise ValidationError(
                {"source_batch": "Партия из другой организации."}
            )
        # Гард: партия должна быть в модуле slaughter (после accept_transfer)
        if self.source_batch_id and self.module_id:
            if self.source_batch.current_module_id != self.module_id:
                raise ValidationError(
                    {
                        "source_batch": (
                            "Партия не в модуле убоя. Сначала примите "
                            "транзфер из откорма."
                        )
                    }
                )
        if self.line_block_id:
            if self.line_block.organization_id != org_id:
                raise ValidationError(
                    {"line_block": "Линия из другой организации."}
                )
            if self.module_id and self.line_block.module_id != self.module_id:
                raise ValidationError(
                    {"line_block": "Линия не принадлежит модулю убоя."}
                )
            if self.line_block.kind != ProductionBlock.Kind.SLAUGHTER_LINE:
                raise ValidationError(
                    {"line_block": "Тип блока должен быть «Линия разделки»."}
                )
        # WITHDRAWAL-GUARD (жёсткое ограничение в модели — явная просьба пользователя)
        if (
            self.source_batch_id
            and self.shift_date is not None
            and self.source_batch.withdrawal_period_ends is not None
            and self.source_batch.withdrawal_period_ends > self.shift_date
        ):
            raise ValidationError(
                {
                    "shift_date": (
                        f"Срок каренции партии ещё не истёк — убой запрещён "
                        f"до {self.source_batch.withdrawal_period_ends}."
                    )
                }
            )
        if self.end_time and self.start_time and self.end_time < self.start_time:
            raise ValidationError(
                {"end_time": "Окончание смены раньше её начала."}
            )
        if self.live_heads_received is not None and self.live_heads_received <= 0:
            raise ValidationError(
                {"live_heads_received": "Должно быть больше нуля."}
            )
        if self.live_weight_kg_total is not None and self.live_weight_kg_total <= 0:
            raise ValidationError(
                {"live_weight_kg_total": "Должно быть больше нуля."}
            )


class SlaughterYield(UUIDModel, TimestampedModel):
    shift = models.ForeignKey(
        SlaughterShift, on_delete=models.CASCADE, related_name="yields"
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="slaughter_yields",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit = models.ForeignKey(
        "nomenclature.Unit",
        on_delete=models.PROTECT,
        related_name="+",
    )
    share_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    output_batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="slaughter_output_of",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["shift", "nomenclature"]
        unique_together = (("shift", "nomenclature"),)
        indexes = [
            models.Index(fields=["shift"]),
            models.Index(fields=["output_batch"]),
        ]
        verbose_name = "Выход продукции"
        verbose_name_plural = "Выход продукции"

    def __str__(self):
        return f"{self.shift.doc_number} · {self.nomenclature.sku} · {self.quantity}"

    def clean(self):
        super().clean()
        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({"quantity": "Должно быть больше нуля."})
        if self.output_batch_id and self.shift_id:
            if self.output_batch.organization_id != self.shift.organization_id:
                raise ValidationError(
                    {"output_batch": "Партия из другой организации."}
                )
            if (
                self.nomenclature_id
                and self.output_batch.nomenclature_id != self.nomenclature_id
            ):
                raise ValidationError(
                    {"output_batch": "Номенклатура партии не совпадает с выходом."}
                )


class SlaughterQualityCheck(UUIDModel, TimestampedModel):
    shift = models.OneToOneField(
        SlaughterShift,
        on_delete=models.CASCADE,
        related_name="quality_check",
    )
    carcass_defect_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    trauma_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    cooling_temperature_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    vet_inspection_passed = models.BooleanField(default=False)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="slaughter_quality_inspections",
    )
    inspected_at = models.DateTimeField()
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Контроль качества смены"
        verbose_name_plural = "Контроль качества смен"

    def __str__(self):
        return f"{self.shift.doc_number} · качество"


class SlaughterLabTest(UUIDModel, TimestampedModel):
    """Отдельный лабораторный показатель (строковая форма — КМАФАнМ, сальмонелла и т.п.)."""

    class Status(models.TextChoices):
        PENDING = "pending", "В работе"
        PASSED = "passed", "Норма"
        FAILED = "failed", "Отклонение"

    shift = models.ForeignKey(
        SlaughterShift, on_delete=models.CASCADE, related_name="lab_tests"
    )
    indicator = models.CharField(max_length=64, db_index=True)
    normal_range = models.CharField(max_length=64)
    actual_value = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    sampled_at = models.DateTimeField(null=True, blank=True)
    result_at = models.DateTimeField(null=True, blank=True)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["shift", "indicator"]
        unique_together = (("shift", "indicator"),)
        indexes = [
            models.Index(fields=["shift", "status"]),
            models.Index(fields=["status"]),
        ]
        verbose_name = "Лаб. показатель смены"
        verbose_name_plural = "Лаб. показатели смен"

    def __str__(self):
        return f"{self.shift.doc_number} · {self.indicator} · {self.get_status_display()}"
