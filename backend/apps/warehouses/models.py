from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class ProductionBlock(UUIDModel, TimestampedModel):
    class Kind(models.TextChoices):
        MATOCHNIK = "matochnik", "Корпус маточника"
        INCUBATION = "incubation", "Инкубационный шкаф"
        HATCHER = "hatcher", "Выводной шкаф"
        FEEDLOT = "feedlot", "Птичник откорма"
        SLAUGHTER_LINE = "slaughter_line", "Линия разделки"
        WAREHOUSE = "warehouse", "Склад"
        VET_STORAGE = "vet_storage", "Склад препаратов"
        MIXER_LINE = "mixer_line", "Линия замеса"
        STORAGE_BIN = "storage_bin", "Бункер готового комбикорма"
        OTHER = "other", "Прочее"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="production_blocks",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="production_blocks",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    kind = models.CharField(max_length=32, choices=Kind.choices)
    area_m2 = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    capacity = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    capacity_unit = models.ForeignKey(
        "nomenclature.Unit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        verbose_name = "Производственный блок"
        verbose_name_plural = "Производственные блоки"

    def __str__(self):
        return f"{self.code} · {self.name}"


class Warehouse(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="warehouses",
    )
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=128)
    production_block = models.ForeignKey(
        ProductionBlock,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="warehouses",
    )
    default_gl_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        verbose_name = "Склад"
        verbose_name_plural = "Склады"

    def __str__(self):
        return f"{self.code} · {self.name}"


class StockMovement(UUIDModel, TimestampedModel):
    class Kind(models.TextChoices):
        INCOMING = "incoming", "Приход"
        OUTGOING = "outgoing", "Расход"
        TRANSFER = "transfer", "Перемещение"
        WRITE_OFF = "write_off", "Списание"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    date = models.DateTimeField(db_index=True)

    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="movements",
    )
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    unit_price_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    amount_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    warehouse_from = models.ForeignKey(
        Warehouse,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements_out",
    )
    warehouse_to = models.ForeignKey(
        Warehouse,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movements_in",
    )

    counterparty = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )

    batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="stock_movements",
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
        ordering = ["-date"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-date"]),
            models.Index(fields=["kind"]),
            models.Index(fields=["batch"]),
            models.Index(fields=["source_content_type", "source_object_id"]),
        ]
        verbose_name = "Движение по складу"
        verbose_name_plural = "Движения по складу"

    def __str__(self):
        return f"{self.doc_number} · {self.get_kind_display()}"

    def clean(self):
        super().clean()
        kind = self.kind
        if kind == self.Kind.INCOMING and self.warehouse_to_id is None:
            raise ValidationError(
                {"warehouse_to": "Для прихода обязательно указать склад-получатель."}
            )
        if kind == self.Kind.OUTGOING and self.warehouse_from_id is None:
            raise ValidationError(
                {"warehouse_from": "Для расхода обязательно указать склад-источник."}
            )
        if kind == self.Kind.TRANSFER and (
            self.warehouse_from_id is None or self.warehouse_to_id is None
        ):
            raise ValidationError(
                "Для перемещения нужны оба склада — источник и получатель."
            )
        if kind == self.Kind.WRITE_OFF and self.warehouse_from_id is None:
            raise ValidationError(
                {"warehouse_from": "Для списания обязательно указать склад-источник."}
            )
        if (
            self.organization_id
            and self.batch_id
            and self.batch.organization_id != self.organization_id
        ):
            raise ValidationError({"batch": "Партия из другой организации."})
