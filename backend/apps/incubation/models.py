from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel
from apps.warehouses.models import ProductionBlock


class IncubationRun(UUIDModel, TimestampedModel):
    """Партия инкубационного яйца, загруженная в инкубатор (с опц. переходом на выводной шкаф)."""

    class Status(models.TextChoices):
        INCUBATING = "incubating", "Инкубация"
        HATCHING = "hatching", "Вывод"
        TRANSFERRED = "transferred", "Передано"
        CANCELLED = "cancelled", "Отменено"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="incubation_runs",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="incubation_runs",
    )
    incubator_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="incubation_runs_as_incubator",
    )
    hatcher_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="incubation_runs_as_hatcher",
    )
    batch = models.ForeignKey(
        "batches.Batch",
        on_delete=models.PROTECT,
        related_name="incubation_runs",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    loaded_date = models.DateField(db_index=True)
    expected_hatch_date = models.DateField()
    actual_hatch_date = models.DateField(null=True, blank=True)

    eggs_loaded = models.PositiveIntegerField()
    eggs_broken_on_load = models.PositiveIntegerField(
        default=0,
        help_text="Яиц разбито/повреждено при закладке (вычитается из eggs_loaded).",
    )
    fertile_eggs = models.PositiveIntegerField(null=True, blank=True)
    hatched_count = models.PositiveIntegerField(null=True, blank=True)
    discarded_count = models.PositiveIntegerField(null=True, blank=True)

    days_total = models.PositiveSmallIntegerField(default=21)
    current_day = models.PositiveSmallIntegerField(null=True, blank=True)

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.INCUBATING,
        db_index=True,
    )
    technologist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="incubation_runs_supervised",
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
        ordering = ["-loaded_date", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["incubator_block", "status"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["organization", "-loaded_date"]),
        ]
        verbose_name = "Инкубационная партия"
        verbose_name_plural = "Инкубационные партии"

    def __str__(self):
        return f"{self.doc_number} · {self.batch.doc_number}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.batch_id and self.batch.organization_id != org_id:
            raise ValidationError({"batch": "Партия из другой организации."})
        if self.incubator_block_id:
            if self.incubator_block.organization_id != org_id:
                raise ValidationError(
                    {"incubator_block": "Блок из другой организации."}
                )
            if (
                self.module_id
                and self.incubator_block.module_id != self.module_id
            ):
                raise ValidationError(
                    {"incubator_block": "Блок не принадлежит модулю инкубации."}
                )
            if self.incubator_block.kind != ProductionBlock.Kind.INCUBATION:
                raise ValidationError(
                    {"incubator_block": "Тип блока должен быть «Инкубационный шкаф»."}
                )
        if self.hatcher_block_id:
            if self.hatcher_block.organization_id != org_id:
                raise ValidationError(
                    {"hatcher_block": "Блок из другой организации."}
                )
            if self.module_id and self.hatcher_block.module_id != self.module_id:
                raise ValidationError(
                    {"hatcher_block": "Блок не принадлежит модулю инкубации."}
                )
            if self.hatcher_block.kind != ProductionBlock.Kind.HATCHER:
                raise ValidationError(
                    {"hatcher_block": "Тип блока должен быть «Выводной шкаф»."}
                )
        if self.eggs_loaded is not None and self.eggs_loaded <= 0:
            raise ValidationError({"eggs_loaded": "Должно быть больше нуля."})
        broken = self.eggs_broken_on_load or 0
        if self.eggs_loaded is not None and broken >= self.eggs_loaded:
            raise ValidationError(
                {"eggs_broken_on_load": "Не может быть больше или равно eggs_loaded."}
            )
        # Arithmetic soft-guard: compare against net_loaded (after breakage)
        net_loaded = (self.eggs_loaded or 0) - broken
        f, h, d = self.fertile_eggs, self.hatched_count, self.discarded_count
        if f is not None and f > net_loaded:
            raise ValidationError(
                {"fertile_eggs": "Оплодотворённых не может быть больше чистой закладки."}
            )
        if f is not None and h is not None and d is not None and (h + d) > f:
            raise ValidationError(
                "Сумма выведенных и отбракованных не может превышать оплодотворённых."
            )


class IncubationRegimeDay(UUIDModel, TimestampedModel):
    run = models.ForeignKey(
        IncubationRun, on_delete=models.CASCADE, related_name="regime_days"
    )
    day = models.PositiveSmallIntegerField()
    temperature_c = models.DecimalField(max_digits=5, decimal_places=2)
    humidity_percent = models.DecimalField(max_digits=5, decimal_places=2)
    egg_turns_per_day = models.PositiveSmallIntegerField(default=0)
    actual_temperature_c = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    actual_humidity_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True
    )
    observed_at = models.DateTimeField(null=True, blank=True)
    observed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["run", "day"]
        unique_together = (("run", "day"),)
        indexes = [models.Index(fields=["run", "day"])]
        verbose_name = "День режима инкубации"
        verbose_name_plural = "Режим инкубации"

    def __str__(self):
        return f"{self.run.doc_number} · день {self.day}"


class MirageInspection(UUIDModel, TimestampedModel):
    """Овоскопия (проверка на свет)."""

    run = models.ForeignKey(
        IncubationRun, on_delete=models.CASCADE, related_name="mirage_inspections"
    )
    inspection_date = models.DateField(db_index=True)
    day_of_incubation = models.PositiveSmallIntegerField()
    inspected_count = models.PositiveIntegerField()
    fertile_count = models.PositiveIntegerField()
    discarded_count = models.PositiveIntegerField(default=0)
    inspector = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mirage_inspections",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-inspection_date"]
        unique_together = (("run", "inspection_date"),)
        indexes = [models.Index(fields=["run", "-inspection_date"])]
        verbose_name = "Овоскопия"
        verbose_name_plural = "Овоскопии"

    def __str__(self):
        return f"{self.run.doc_number} · {self.inspection_date}"

    def clean(self):
        super().clean()
        if (
            self.fertile_count is not None
            and self.discarded_count is not None
            and self.inspected_count is not None
            and (self.fertile_count + self.discarded_count) > self.inspected_count
        ):
            raise ValidationError(
                "Сумма оплодотворённых и отбракованных не может превышать осмотренных."
            )
