from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class BreedingHerd(UUIDModel, TimestampedModel):
    """Долгоживущее родительское стадо в корпусе маточника."""

    class Direction(models.TextChoices):
        BROILER_PARENT = "broiler_parent", "Бройлерное родительское"
        LAYER_PARENT = "layer_parent", "Яичное родительское"

    class Status(models.TextChoices):
        GROWING = "growing", "Разгон"
        PRODUCING = "producing", "Продуктив"
        DEPOPULATED = "depopulated", "Снято"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="breeding_herds",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="breeding_herds",
    )
    block = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="breeding_herds",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    direction = models.CharField(
        max_length=16, choices=Direction.choices, db_index=True
    )
    source_counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="+",
    )
    source_batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="spawned_breeding_herds",
    )
    placed_at = models.DateField(db_index=True)
    initial_heads = models.PositiveIntegerField()
    current_heads = models.PositiveIntegerField()
    age_weeks_at_placement = models.PositiveSmallIntegerField()
    current_age_weeks = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.GROWING,
        db_index=True,
    )
    technologist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="matochnik_herds_supervised",
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
        ordering = ["-placed_at", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "-placed_at"]),
            models.Index(fields=["block", "status"]),
            models.Index(fields=["direction", "status"]),
        ]
        verbose_name = "Родительское стадо"
        verbose_name_plural = "Родительские стада"

    def __str__(self):
        return f"{self.doc_number} · {self.block.code}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.source_counterparty_id
            and self.source_counterparty.organization_id != org_id
        ):
            raise ValidationError(
                {"source_counterparty": "Контрагент из другой организации."}
            )
        if self.source_batch_id and self.source_batch.organization_id != org_id:
            raise ValidationError(
                {"source_batch": "Партия из другой организации."}
            )
        if self.block_id:
            if self.block.organization_id != org_id:
                raise ValidationError({"block": "Блок из другой организации."})
            if self.module_id and self.block.module_id != self.module_id:
                raise ValidationError(
                    {"block": "Блок не принадлежит модулю стада."}
                )
        if (
            self.initial_heads is not None
            and self.current_heads is not None
            and self.current_heads > self.initial_heads
        ):
            raise ValidationError(
                {"current_heads": "Текущее поголовье не может превышать начальное."}
            )


class DailyEggProduction(UUIDModel, TimestampedModel):
    herd = models.ForeignKey(
        BreedingHerd,
        on_delete=models.PROTECT,
        related_name="daily_egg_records",
    )
    date = models.DateField(db_index=True)
    eggs_collected = models.PositiveIntegerField()
    unfit_eggs = models.PositiveIntegerField(default=0)
    outgoing_batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="egg_production_records",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = (("herd", "date"),)
        indexes = [
            models.Index(fields=["herd", "-date"]),
            models.Index(fields=["outgoing_batch"]),
        ]
        verbose_name = "Суточный яйцесбор"
        verbose_name_plural = "Суточный яйцесбор"

    def __str__(self):
        return f"{self.herd.doc_number} · {self.date} · {self.eggs_collected} шт"

    def clean(self):
        super().clean()
        if (
            self.eggs_collected is not None
            and self.unfit_eggs is not None
            and self.unfit_eggs > self.eggs_collected
        ):
            raise ValidationError(
                {"unfit_eggs": "Брак не может превышать собранное."}
            )
        if self.outgoing_batch_id and self.herd_id:
            if self.outgoing_batch.organization_id != self.herd.organization_id:
                raise ValidationError(
                    {"outgoing_batch": "Партия из другой организации."}
                )


class BreedingMortality(UUIDModel, TimestampedModel):
    herd = models.ForeignKey(
        BreedingHerd,
        on_delete=models.PROTECT,
        related_name="mortality_records",
    )
    date = models.DateField(db_index=True)
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
        unique_together = (("herd", "date"),)
        indexes = [models.Index(fields=["herd", "-date"])]
        verbose_name = "Падёж стада"
        verbose_name_plural = "Падёж стада"

    def __str__(self):
        return f"{self.herd.doc_number} · {self.date} · {self.dead_count} гол"

    def clean(self):
        super().clean()
        if self.dead_count is not None and self.dead_count <= 0:
            raise ValidationError({"dead_count": "Должно быть больше нуля."})


class BreedingFeedConsumption(UUIDModel, TimestampedModel):
    herd = models.ForeignKey(
        BreedingHerd,
        on_delete=models.PROTECT,
        related_name="feed_consumption_records",
    )
    date = models.DateField(db_index=True)
    feed_batch = models.ForeignKey(
        "feed.FeedBatch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="matochnik_consumption_records",
    )
    quantity_kg = models.DecimalField(max_digits=12, decimal_places=3)
    per_head_g = models.DecimalField(
        max_digits=8, decimal_places=3, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = (("herd", "date", "feed_batch"),)
        indexes = [
            models.Index(fields=["herd", "-date"]),
            models.Index(fields=["feed_batch"]),
        ]
        verbose_name = "Суточный расход корма (маточник)"
        verbose_name_plural = "Суточный расход корма (маточник)"

    def __str__(self):
        return f"{self.herd.doc_number} · {self.date} · {self.quantity_kg} кг"

    def clean(self):
        super().clean()
        if self.feed_batch_id and self.herd_id:
            if self.feed_batch.organization_id != self.herd.organization_id:
                raise ValidationError(
                    {"feed_batch": "Партия корма из другой организации."}
                )
        if self.quantity_kg is not None and self.quantity_kg <= 0:
            raise ValidationError({"quantity_kg": "Должно быть больше нуля."})
