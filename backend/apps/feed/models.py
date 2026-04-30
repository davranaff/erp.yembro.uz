from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


# ─── Recipes ───────────────────────────────────────────────────────────────


class Recipe(UUIDModel, TimestampedModel):
    class Direction(models.TextChoices):
        BROILER = "broiler", "Бройлер"
        LAYER = "layer", "Несушка"
        PARENT = "parent", "Родительское стадо"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="recipes",
    )
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    direction = models.CharField(
        max_length=16, choices=Direction.choices, db_index=True
    )
    age_range = models.CharField(max_length=32, blank=True)
    is_medicated = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["code"]
        unique_together = (("organization", "code"),)
        indexes = [
            models.Index(fields=["organization", "direction"]),
            models.Index(fields=["organization", "is_active"]),
        ]
        verbose_name = "Рецептура"
        verbose_name_plural = "Рецептуры"

    def __str__(self):
        return f"{self.code} · {self.name}"


class RecipeVersion(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        ACTIVE = "active", "Действующая"
        ARCHIVED = "archived", "Архив"

    recipe = models.ForeignKey(
        Recipe, on_delete=models.PROTECT, related_name="versions"
    )
    version_number = models.PositiveSmallIntegerField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True
    )
    effective_from = models.DateField()

    target_protein_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_fat_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_fibre_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_lysine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_methionine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_threonine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    target_me_kcal_per_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    comment = models.TextField(blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["recipe", "-version_number"]
        unique_together = (("recipe", "version_number"),)
        indexes = [
            models.Index(fields=["recipe", "status"]),
            models.Index(fields=["status", "effective_from"]),
        ]
        verbose_name = "Версия рецептуры"
        verbose_name_plural = "Версии рецептур"

    def __str__(self):
        return f"{self.recipe.code} v.{self.version_number}"

    def clean(self):
        super().clean()
        if self.status == self.Status.ACTIVE and self.recipe_id:
            qs = RecipeVersion.objects.filter(
                recipe_id=self.recipe_id, status=self.Status.ACTIVE
            )
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                raise ValidationError(
                    "У рецептуры уже есть действующая версия."
                )


class RecipeComponent(UUIDModel, TimestampedModel):
    recipe_version = models.ForeignKey(
        RecipeVersion, on_delete=models.CASCADE, related_name="components"
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="recipe_components",
    )
    share_percent = models.DecimalField(max_digits=7, decimal_places=4)
    min_share_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )
    max_share_percent = models.DecimalField(
        max_digits=7, decimal_places=4, null=True, blank=True
    )

    protein_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fat_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fibre_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    lysine_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    methionine_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    threonine_override = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    me_kcal_per_kg_override = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )

    is_medicated = models.BooleanField(default=False)
    withdrawal_period_days = models.PositiveSmallIntegerField(default=0)
    vet_drug = models.ForeignKey(
        "vet.VetDrug",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_recipe_components",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["recipe_version", "sort_order"]
        unique_together = (("recipe_version", "nomenclature"),)
        indexes = [
            models.Index(fields=["recipe_version"]),
            models.Index(fields=["nomenclature"]),
        ]
        verbose_name = "Компонент рецептуры"
        verbose_name_plural = "Компоненты рецептур"

    def __str__(self):
        return f"{self.recipe_version} · {self.nomenclature.sku} {self.share_percent}%"


class NomenclatureNutritionProfile(UUIDModel, TimestampedModel):
    """Референсный типовой нутрициональный профиль сырья."""

    nomenclature = models.OneToOneField(
        "nomenclature.NomenclatureItem",
        on_delete=models.CASCADE,
        related_name="nutrition_profile",
    )
    protein_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fat_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fibre_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    lysine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    methionine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    threonine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    me_kcal_per_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    humidity_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    ash_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Нутрициональный профиль"
        verbose_name_plural = "Нутрициональные профили"

    def __str__(self):
        return f"{self.nomenclature.sku} nutrition"


# ─── Raw material batches ──────────────────────────────────────────────────


class RawMaterialBatch(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        QUARANTINE = "quarantine", "На карантине"
        AVAILABLE = "available", "Доступна"
        REJECTED = "rejected", "Отклонена"
        DEPLETED = "depleted", "Исчерпана"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    supplier = models.ForeignKey(
        "counterparties.Counterparty",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    purchase = models.ForeignKey(
        "purchases.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="raw_material_batches",
    )
    received_date = models.DateField(db_index=True)
    storage_bin = models.CharField(
        max_length=64, blank=True,
        help_text="Бункер/секция склада (плоская строка, например «БК-3»).",
    )
    # Веса. quantity == settlement (зачётный) для совместимости со старым кодом.
    # gross_weight_kg — физический вес на весах. settlement_weight_kg —
    # после применения формулы Дюваля и/или поправки на сорность.
    quantity = models.DecimalField(max_digits=18, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=18, decimal_places=3)
    gross_weight_kg = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True,
        help_text="Физический вес на весах при приёмке.",
    )
    settlement_weight_kg = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True,
        help_text="Зачётный вес после поправки на влажность/сорность (== quantity).",
    )
    # Влажность / сорность (snapshot на момент приёмки)
    moisture_pct_actual = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Фактическая влажность сырья (%).",
    )
    moisture_pct_base = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Базисная влажность (snapshot из nomenclature на момент приёмки).",
    )
    dockage_pct_actual = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Сорность %.",
    )
    shrinkage_pct = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text="Итоговая поправка % (Дюваль + сорность).",
    )
    unit = models.ForeignKey(
        "nomenclature.Unit",
        on_delete=models.PROTECT,
        related_name="+",
    )
    price_per_unit_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUARANTINE,
        db_index=True,
    )
    quarantine_until = models.DateField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-received_date", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["nomenclature", "status"]),
            models.Index(fields=["organization", "-received_date"]),
            models.Index(fields=["warehouse", "status"]),
        ]
        verbose_name = "Партия сырья"
        verbose_name_plural = "Партии сырья"

    def __str__(self):
        return f"{self.doc_number} · {self.nomenclature.sku}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.supplier_id and self.supplier.organization_id != org_id:
            raise ValidationError({"supplier": "Поставщик из другой организации."})
        if self.purchase_id and self.purchase.organization_id != org_id:
            raise ValidationError({"purchase": "Закуп из другой организации."})
        if self.warehouse_id:
            if self.warehouse.organization_id != org_id:
                raise ValidationError({"warehouse": "Склад из другой организации."})
            if self.module_id and self.warehouse.module_id != self.module_id:
                raise ValidationError(
                    {"warehouse": "Склад не принадлежит модулю партии."}
                )
        if (
            self.quantity is not None
            and self.current_quantity is not None
            and self.current_quantity > self.quantity
        ):
            raise ValidationError(
                {"current_quantity": "Остаток не может превышать начальное количество."}
            )


# ─── Lab results ───────────────────────────────────────────────────────────


class LabResult(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "В работе"
        PASSED = "passed", "Принято"
        FAILED = "failed", "Отклонено"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="lab_results",
    )
    doc_number = models.CharField(max_length=32, db_index=True)

    subject_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        related_name="+",
    )
    subject_object_id = models.UUIDField()
    subject = GenericForeignKey("subject_content_type", "subject_object_id")

    sampled_at = models.DateTimeField(db_index=True)
    result_received_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    protein_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fat_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    fibre_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    humidity_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    ash_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    lysine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    methionine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    threonine_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True
    )
    me_kcal_per_kg = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True
    )
    additional_findings = models.JSONField(null=True, blank=True)

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-sampled_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["subject_content_type", "subject_object_id"]),
            models.Index(fields=["organization", "-sampled_at"]),
        ]
        verbose_name = "Лабораторный анализ"
        verbose_name_plural = "Лабораторные анализы"

    def __str__(self):
        return f"{self.doc_number} · {self.get_status_display()}"

    def clean(self):
        super().clean()
        if self.subject_content_type_id:
            model = self.subject_content_type.model
            if model not in {"rawmaterialbatch", "feedbatch"}:
                raise ValidationError(
                    {"subject_content_type": "Анализ возможен для партии сырья или готового комбикорма."}
                )


# ─── Production ────────────────────────────────────────────────────────────


class ProductionTask(UUIDModel, TimestampedModel):
    class Shift(models.TextChoices):
        DAY = "day", "День"
        NIGHT = "night", "Ночь"

    class Status(models.TextChoices):
        PLANNED = "planned", "План"
        RUNNING = "running", "В работе"
        PAUSED = "paused", "Пауза"
        DONE = "done", "Закрыто"
        CANCELLED = "cancelled", "Отменено"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="production_tasks",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="production_tasks",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    recipe_version = models.ForeignKey(
        RecipeVersion,
        on_delete=models.PROTECT,
        related_name="production_tasks",
    )
    production_line = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="production_tasks",
    )
    shift = models.CharField(max_length=8, choices=Shift.choices, default=Shift.DAY)
    scheduled_at = models.DateTimeField(db_index=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    planned_quantity_kg = models.DecimalField(max_digits=18, decimal_places=3)
    actual_quantity_kg = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PLANNED,
        db_index=True,
    )
    is_medicated = models.BooleanField(default=False)
    withdrawal_period_days = models.PositiveSmallIntegerField(default=0)

    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="feed_tasks_operated",
    )
    technologist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="feed_tasks_created",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_at", "-created_at"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["recipe_version", "status"]),
            models.Index(fields=["production_line", "scheduled_at"]),
            models.Index(fields=["organization", "-scheduled_at"]),
        ]
        verbose_name = "Задание на замес"
        verbose_name_plural = "Задания на замес"

    def __str__(self):
        return f"{self.doc_number} · {self.recipe_version}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.production_line_id
            and self.production_line.organization_id != org_id
        ):
            raise ValidationError(
                {"production_line": "Линия из другой организации."}
            )
        if (
            self.production_line_id
            and self.module_id
            and self.production_line.module_id != self.module_id
        ):
            raise ValidationError(
                {"production_line": "Линия не принадлежит модулю задания."}
            )
        if (
            self.recipe_version_id
            and self.recipe_version.recipe.organization_id != org_id
        ):
            raise ValidationError(
                {"recipe_version": "Рецептура из другой организации."}
            )


class ProductionTaskComponent(UUIDModel, TimestampedModel):
    task = models.ForeignKey(
        ProductionTask, on_delete=models.CASCADE, related_name="components"
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="production_task_components",
    )
    source_batch = models.ForeignKey(
        RawMaterialBatch,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="consumed_in_tasks",
    )
    planned_quantity = models.DecimalField(max_digits=18, decimal_places=3)
    actual_quantity = models.DecimalField(
        max_digits=18, decimal_places=3, null=True, blank=True
    )
    planned_price_per_unit_uzs = models.DecimalField(max_digits=18, decimal_places=2)
    actual_price_per_unit_uzs = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    lab_result_snapshot = models.ForeignKey(
        LabResult,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["task", "sort_order"]
        unique_together = (("task", "nomenclature"),)
        indexes = [
            models.Index(fields=["task"]),
            models.Index(fields=["source_batch"]),
            models.Index(fields=["nomenclature"]),
        ]
        verbose_name = "Компонент задания"
        verbose_name_plural = "Компоненты заданий"

    def __str__(self):
        return f"{self.task.doc_number} · {self.nomenclature.sku}"

    def clean(self):
        super().clean()
        if self.source_batch_id and self.nomenclature_id:
            if self.source_batch.nomenclature_id != self.nomenclature_id:
                raise ValidationError(
                    {"source_batch": "Партия сырья не совпадает с номенклатурой компонента."}
                )
        if self.source_batch_id and self.task_id:
            if (
                self.source_batch.organization_id
                != self.task.organization_id
            ):
                raise ValidationError(
                    {"source_batch": "Партия сырья из другой организации."}
                )


class FeedBatch(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        QUALITY_CHECK = "quality_check", "На лаб. контроле"
        APPROVED = "approved", "Одобрена"
        REJECTED = "rejected", "Отклонена"
        DEPLETED = "depleted", "Исчерпана"

    class PassportStatus(models.TextChoices):
        PENDING = "pending", "В работе"
        PASSED = "passed", "Норма"
        FAILED = "failed", "Отклонён"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feed_batches",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="feed_batches",
    )
    doc_number = models.CharField(max_length=64, db_index=True)
    produced_by_task = models.OneToOneField(
        ProductionTask,
        on_delete=models.PROTECT,
        related_name="produced_feed_batch",
    )
    recipe_version = models.ForeignKey(
        RecipeVersion,
        on_delete=models.PROTECT,
        related_name="feed_batches",
    )
    produced_at = models.DateTimeField(db_index=True)
    quantity_kg = models.DecimalField(max_digits=18, decimal_places=3)
    current_quantity_kg = models.DecimalField(max_digits=18, decimal_places=3)
    unit_cost_uzs = models.DecimalField(max_digits=18, decimal_places=6)
    total_cost_uzs = models.DecimalField(max_digits=18, decimal_places=2)

    storage_bin = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="stored_feed_batches",
    )
    storage_warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_batches",
    )

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.QUALITY_CHECK,
        db_index=True,
    )
    is_medicated = models.BooleanField(default=False)
    withdrawal_period_days = models.PositiveSmallIntegerField(default=0)
    withdrawal_period_ends = models.DateField(null=True, blank=True, db_index=True)
    quality_passport_status = models.CharField(
        max_length=16,
        choices=PassportStatus.choices,
        default=PassportStatus.PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-produced_at", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["recipe_version", "status"]),
            models.Index(fields=["organization", "-produced_at"]),
            models.Index(fields=["storage_bin", "status"]),
            models.Index(fields=["is_medicated", "withdrawal_period_ends"]),
        ]
        verbose_name = "Партия готового корма"
        verbose_name_plural = "Партии готового корма"

    def __str__(self):
        return f"{self.doc_number} · {self.recipe_version}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.produced_by_task_id
            and self.produced_by_task.organization_id != org_id
        ):
            raise ValidationError(
                {"produced_by_task": "Задание из другой организации."}
            )
        if (
            self.produced_by_task_id
            and self.recipe_version_id
            and self.produced_by_task.recipe_version_id != self.recipe_version_id
        ):
            raise ValidationError(
                {"recipe_version": "Версия рецепта не совпадает с версией задания."}
            )
        if self.storage_bin_id:
            if self.storage_bin.organization_id != org_id:
                raise ValidationError(
                    {"storage_bin": "Бункер из другой организации."}
                )
            if self.module_id and self.storage_bin.module_id != self.module_id:
                raise ValidationError(
                    {"storage_bin": "Бункер не принадлежит модулю."}
                )
        if self.storage_warehouse_id:
            if self.storage_warehouse.organization_id != org_id:
                raise ValidationError(
                    {"storage_warehouse": "Склад из другой организации."}
                )
            if (
                self.module_id
                and self.storage_warehouse.module_id != self.module_id
            ):
                raise ValidationError(
                    {"storage_warehouse": "Склад не принадлежит модулю."}
                )
        if (
            self.quantity_kg is not None
            and self.current_quantity_kg is not None
            and self.current_quantity_kg > self.quantity_kg
        ):
            raise ValidationError(
                {"current_quantity_kg": "Остаток не может превышать выпуск."}
            )


# ─── Consumption planning ──────────────────────────────────────────────────


class FeedShrinkageProfile(UUIDModel, TimestampedModel):
    """Профиль периодической усушки сырья / готового корма.

    Привязан либо к номенклатурной позиции сырья (target_type=INGREDIENT),
    либо к рецептуре готового корма (target_type=FEED_TYPE — рецептура задаёт
    «тип готового корма», профиль действует на все её версии и партии).

    Опциональная привязка к складу: NULL = «для всех складов организации»,
    конкретный склад побеждает общий.
    """

    class TargetType(models.TextChoices):
        INGREDIENT = "ingredient", "Ингредиент (сырьё)"
        FEED_TYPE = "feed_type", "Тип готового корма"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feed_shrinkage_profiles",
    )
    target_type = models.CharField(
        max_length=16, choices=TargetType.choices, db_index=True
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_shrinkage_profiles",
        help_text="Заполняется при target_type=ingredient.",
    )
    recipe = models.ForeignKey(
        Recipe,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_shrinkage_profiles",
        help_text="Заполняется при target_type=feed_type. Один профиль действует "
                  "на все версии рецепта и все партии готового корма по нему.",
    )
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_shrinkage_profiles",
        help_text="NULL = «для всех складов»; конкретный склад побеждает общий.",
    )
    period_days = models.PositiveSmallIntegerField(
        help_text="Каждые сколько дней применяется процент усушки.",
    )
    percent_per_period = models.DecimalField(
        max_digits=6,
        decimal_places=3,
        help_text="Сколько % от текущего остатка списывается за период (compound).",
    )
    max_total_percent = models.DecimalField(
        max_digits=6, decimal_places=3, null=True, blank=True,
        help_text="Верхний предел накопленной усушки на партию (% от initial). "
                  "NULL = без предела.",
    )
    stop_after_days = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Не списывать дольше N дней с поступления партии. NULL = без ограничения.",
    )
    starts_after_days = models.PositiveSmallIntegerField(
        default=0,
        help_text="Грейс-период: первые N дней после поступления усушка не считается.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    note = models.TextField(blank=True)

    class Meta:
        ordering = ["organization", "target_type", "-updated_at"]
        constraints = [
            models.CheckConstraint(
                name="feed_shrinkage_profile_target_xor",
                check=(
                    models.Q(target_type="ingredient", nomenclature__isnull=False, recipe__isnull=True)
                    | models.Q(target_type="feed_type", recipe__isnull=False, nomenclature__isnull=True)
                ),
            ),
            models.CheckConstraint(
                name="feed_shrinkage_profile_period_positive",
                check=models.Q(period_days__gt=0),
            ),
            models.CheckConstraint(
                name="feed_shrinkage_profile_pct_range",
                check=models.Q(percent_per_period__gte=0)
                & models.Q(percent_per_period__lte=100),
            ),
            models.CheckConstraint(
                name="feed_shrinkage_profile_max_pct_range",
                check=models.Q(max_total_percent__isnull=True)
                | (models.Q(max_total_percent__gte=0) & models.Q(max_total_percent__lte=100)),
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "target_type", "is_active"]),
            models.Index(fields=["nomenclature", "warehouse"]),
            models.Index(fields=["recipe", "warehouse"]),
        ]
        verbose_name = "Профиль усушки"
        verbose_name_plural = "Профили усушки"

    def __str__(self) -> str:
        target = self.nomenclature_id or self.recipe_id
        return f"{self.get_target_type_display()} · {target} · {self.percent_per_period}%/{self.period_days}д"

    def clean(self):
        super().clean()
        if self.target_type == self.TargetType.INGREDIENT:
            if self.nomenclature_id is None:
                raise ValidationError({"nomenclature": "Обязательно для target_type=ingredient."})
            if self.recipe_id is not None:
                raise ValidationError({"recipe": "Не должно быть заполнено при target_type=ingredient."})
        elif self.target_type == self.TargetType.FEED_TYPE:
            if self.recipe_id is None:
                raise ValidationError({"recipe": "Обязательно для target_type=feed_type."})
            if self.nomenclature_id is not None:
                raise ValidationError({"nomenclature": "Не должно быть заполнено при target_type=feed_type."})
        if self.recipe_id and self.organization_id:
            if self.recipe.organization_id != self.organization_id:
                raise ValidationError({"recipe": "Рецепт из другой организации."})
        if self.warehouse_id and self.organization_id:
            if self.warehouse.organization_id != self.organization_id:
                raise ValidationError({"warehouse": "Склад из другой организации."})


class FeedLotShrinkageState(UUIDModel, TimestampedModel):
    """Состояние усушки конкретной партии.

    Создаётся при первом срабатывании воркера для партии, обновляется на каждое
    списание. Хранит накопленные потери и дату последнего цикла, чтобы алгоритм
    мог считать «сколько полных периодов прошло с прошлого раза».
    """

    class LotType(models.TextChoices):
        RAW_ARRIVAL = "raw_arrival", "Партия сырья"
        PRODUCTION_BATCH = "production_batch", "Партия готового корма"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feed_lot_shrinkage_states",
    )
    lot_type = models.CharField(max_length=24, choices=LotType.choices, db_index=True)
    lot_id = models.UUIDField(db_index=True)

    profile = models.ForeignKey(
        FeedShrinkageProfile,
        on_delete=models.PROTECT,
        related_name="lot_states",
    )
    initial_quantity = models.DecimalField(max_digits=16, decimal_places=3)
    accumulated_loss = models.DecimalField(
        max_digits=16, decimal_places=3, default=0,
    )
    last_applied_on = models.DateField(
        null=True, blank=True,
        help_text="Дата последнего цикла списания. NULL до первого применения.",
    )
    is_frozen = models.BooleanField(
        default=False, db_index=True,
        help_text="True когда достигнут max_total_percent / stop_after_days / остаток исчерпан.",
    )

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["lot_type", "lot_id"],
                name="feed_lot_shrinkage_state_unique_lot",
            ),
            models.CheckConstraint(
                name="feed_lot_shrinkage_state_loss_within_initial",
                check=models.Q(accumulated_loss__gte=0)
                & models.Q(accumulated_loss__lte=models.F("initial_quantity")),
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "lot_type", "is_frozen"]),
            models.Index(fields=["profile", "is_frozen"]),
        ]
        verbose_name = "Состояние усушки партии"
        verbose_name_plural = "Состояния усушки партий"

    def __str__(self) -> str:
        return f"{self.get_lot_type_display()} {self.lot_id} · loss={self.accumulated_loss}"


class FeedConsumptionPlan(UUIDModel, TimestampedModel):
    class Status(models.TextChoices):
        FORECAST = "forecast", "Прогноз"
        COMMITTED = "committed", "Подтверждён"
        FULFILLED = "fulfilled", "Исполнен"
        CANCELLED = "cancelled", "Отменён"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="feed_consumption_plans",
    )
    consumer_module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="feed_consumption_plans",
    )
    consumer_batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_consumption_plans",
    )
    consumer_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="feed_consumption_plans",
    )
    recipe = models.ForeignKey(
        Recipe, on_delete=models.PROTECT, related_name="consumption_plans"
    )
    week_start = models.DateField(db_index=True)
    planned_quantity_kg = models.DecimalField(max_digits=18, decimal_places=3)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.FORECAST,
        db_index=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["week_start", "consumer_module"]
        indexes = [
            models.Index(fields=["organization", "week_start"]),
            models.Index(fields=["consumer_module", "status"]),
            models.Index(fields=["recipe", "week_start"]),
        ]
        verbose_name = "План потребления корма"
        verbose_name_plural = "Планы потребления корма"

    def __str__(self):
        return f"{self.recipe.code} · {self.week_start} · {self.consumer_module.code}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if (
            self.consumer_batch_id
            and self.consumer_batch.organization_id != org_id
        ):
            raise ValidationError(
                {"consumer_batch": "Партия из другой организации."}
            )
        if self.consumer_block_id:
            if self.consumer_block.organization_id != org_id:
                raise ValidationError(
                    {"consumer_block": "Блок из другой организации."}
                )
            if (
                self.consumer_module_id
                and self.consumer_block.module_id != self.consumer_module_id
            ):
                raise ValidationError(
                    {"consumer_block": "Блок не принадлежит модулю-потребителю."}
                )
        if self.recipe_id and self.recipe.organization_id != org_id:
            raise ValidationError({"recipe": "Рецептура из другой организации."})
