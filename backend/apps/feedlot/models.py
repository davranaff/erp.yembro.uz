from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel
from apps.warehouses.models import ProductionBlock


class FeedlotBatch(UUIDModel, TimestampedModel):
    """Операционная партия птицы на откорме в птичнике."""

    class Status(models.TextChoices):
        PLACED = "placed", "Посажено"
        GROWING = "growing", "Откорм"
        READY_SLAUGHTER = "ready_slaughter", "К съёму"
        SHIPPED = "shipped", "Передано на убой"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feedlot_batches",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="feedlot_batches",
    )
    house_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="feedlot_batches",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        on_delete=models.PROTECT,
        related_name="feedlot_placements",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    placed_date = models.DateField(db_index=True)
    target_slaughter_date = models.DateField(null=True, blank=True)
    target_weight_kg = models.DecimalField(
        max_digits=6, decimal_places=3, default=Decimal("2.500")
    )
    initial_heads = models.PositiveIntegerField()
    current_heads = models.PositiveIntegerField()
    status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PLACED,
        db_index=True,
    )
    technologist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="feedlot_batches_supervised",
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
        ordering = ["-placed_date", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["house_block", "status"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["organization", "-placed_date"]),
        ]
        verbose_name = "Партия откорма"
        verbose_name_plural = "Партии откорма"

    def __str__(self):
        return f"{self.doc_number} · {self.batch.doc_number}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.batch_id and self.batch.organization_id != org_id:
            raise ValidationError({"batch": "Партия из другой организации."})
        if self.house_block_id:
            if self.house_block.organization_id != org_id:
                raise ValidationError({"house_block": "Блок из другой организации."})
            if self.module_id and self.house_block.module_id != self.module_id:
                raise ValidationError(
                    {"house_block": "Блок не принадлежит модулю откорма."}
                )
            if self.house_block.kind != ProductionBlock.Kind.FEEDLOT:
                raise ValidationError(
                    {"house_block": "Тип блока должен быть «Птичник откорма»."}
                )
        if (
            self.initial_heads is not None
            and self.current_heads is not None
            and self.current_heads > self.initial_heads
        ):
            raise ValidationError(
                {"current_heads": "Текущее поголовье не может превышать начальное."}
            )


class DailyWeighing(UUIDModel, TimestampedModel):
    feedlot_batch = models.ForeignKey(
        FeedlotBatch, on_delete=models.CASCADE, related_name="weighings"
    )
    date = models.DateField(db_index=True)
    day_of_age = models.PositiveSmallIntegerField()
    sample_size = models.PositiveIntegerField()
    avg_weight_kg = models.DecimalField(max_digits=6, decimal_places=3)
    gain_kg = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["feedlot_batch", "day_of_age"]
        unique_together = (("feedlot_batch", "day_of_age"),)
        indexes = [models.Index(fields=["feedlot_batch", "-date"])]
        verbose_name = "Контрольное взвешивание"
        verbose_name_plural = "Контрольные взвешивания"

    def __str__(self):
        return f"{self.feedlot_batch.doc_number} · д.{self.day_of_age} · {self.avg_weight_kg} кг"

    def clean(self):
        super().clean()
        if self.sample_size is not None and self.sample_size <= 0:
            raise ValidationError({"sample_size": "Должно быть больше нуля."})
        if self.avg_weight_kg is not None and self.avg_weight_kg <= 0:
            raise ValidationError({"avg_weight_kg": "Должно быть больше нуля."})


class FeedlotFeedConsumption(UUIDModel, TimestampedModel):
    class FeedType(models.TextChoices):
        START = "start", "Старт"
        GROWTH = "growth", "Рост"
        FINISH = "finish", "Финиш"

    feedlot_batch = models.ForeignKey(
        FeedlotBatch,
        on_delete=models.CASCADE,
        related_name="feed_consumption_periods",
    )
    period_from_day = models.PositiveSmallIntegerField()
    period_to_day = models.PositiveSmallIntegerField()
    feed_type = models.CharField(
        max_length=16, choices=FeedType.choices, db_index=True
    )
    feed_batch = models.ForeignKey(
        "feed.FeedBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feedlot_consumption_periods",
    )
    total_kg = models.DecimalField(max_digits=12, decimal_places=3)
    per_head_g = models.DecimalField(
        max_digits=10, decimal_places=3, null=True, blank=True
    )
    period_fcr = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["feedlot_batch", "period_from_day"]
        unique_together = (("feedlot_batch", "period_from_day", "feed_type"),)
        indexes = [
            models.Index(fields=["feedlot_batch", "feed_type"]),
            models.Index(fields=["feed_batch"]),
        ]
        verbose_name = "Расход корма (откорм)"
        verbose_name_plural = "Расход корма (откорм)"

    def __str__(self):
        return (
            f"{self.feedlot_batch.doc_number} · {self.period_from_day}-{self.period_to_day}"
            f" · {self.get_feed_type_display()}"
        )

    def clean(self):
        super().clean()
        if (
            self.period_from_day is not None
            and self.period_to_day is not None
            and self.period_to_day < self.period_from_day
        ):
            raise ValidationError(
                {"period_to_day": "Конец периода раньше его начала."}
            )
        if self.feed_batch_id and self.feedlot_batch_id:
            if (
                self.feed_batch.organization_id
                != self.feedlot_batch.organization_id
            ):
                raise ValidationError(
                    {"feed_batch": "Партия корма из другой организации."}
                )
        if self.total_kg is not None and self.total_kg <= 0:
            raise ValidationError({"total_kg": "Должно быть больше нуля."})


class FeedlotMortality(UUIDModel, TimestampedModel):
    feedlot_batch = models.ForeignKey(
        FeedlotBatch,
        on_delete=models.CASCADE,
        related_name="mortality_records",
    )
    date = models.DateField(db_index=True)
    day_of_age = models.PositiveSmallIntegerField()
    dead_count = models.PositiveIntegerField()
    cause = models.CharField(max_length=128, blank=True)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-date"]
        unique_together = (("feedlot_batch", "date"),)
        indexes = [models.Index(fields=["feedlot_batch", "-date"])]
        verbose_name = "Падёж (откорм)"
        verbose_name_plural = "Падёж (откорм)"

    def __str__(self):
        return f"{self.feedlot_batch.doc_number} · {self.date} · {self.dead_count}"

    def clean(self):
        super().clean()
        if self.dead_count is not None and self.dead_count <= 0:
            raise ValidationError({"dead_count": "Должно быть больше нуля."})
