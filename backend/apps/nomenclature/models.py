from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class Unit(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="units",
    )
    code = models.CharField(max_length=16)
    name = models.CharField(max_length=64)

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        verbose_name = "Единица измерения"
        verbose_name_plural = "Единицы измерения"

    def __str__(self):
        return self.code


class Category(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="categories",
    )
    name = models.CharField(max_length=128)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    module = models.ForeignKey(
        "modules.Module",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="nomenclature_categories",
        help_text=(
            "К какому модулю относится категория. "
            "Если NULL — категория общая (не привязана). "
            "Используется для фильтрации SKU в формах модулей."
        ),
    )
    default_gl_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="categories",
    )

    class Meta:
        ordering = ["name"]
        unique_together = (("organization", "name"),)
        indexes = [
            models.Index(fields=["organization", "module"]),
        ]
        verbose_name = "Категория"
        verbose_name_plural = "Категории"

    def __str__(self):
        return self.name


class NomenclatureItem(UUIDModel, TimestampedModel):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="nomenclature_items",
    )
    sku = models.CharField(max_length=64)
    name = models.CharField(max_length=255)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="items"
    )
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="items")
    default_gl_subaccount = models.ForeignKey(
        "accounting.GLSubaccount",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="items",
    )
    barcode = models.CharField(max_length=64, blank=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    # Базисная влажность для расчёта зачётного веса при приёмке сырья
    # (формула Дюваля). null = поле не применимо к этому SKU.
    # Типичные значения: 14% (зерно по ГОСТ 13586.5), 12% (шрот), 10% (премикс).
    base_moisture_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text=(
            "Базисная влажность %. Используется при приёмке сырья "
            "для расчёта зачётного веса по формуле Дюваля. "
            "Зерно/ГОСТ 13586.5 — 14%, шрот — 12%, премикс — 10%."
        ),
    )

    class Meta:
        ordering = ["sku"]
        unique_together = (("organization", "sku"),)
        verbose_name = "Номенклатура"
        verbose_name_plural = "Номенклатура"

    def __str__(self):
        return f"{self.sku} · {self.name}"
