from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimestampedModel, UUIDModel


class DrugType(models.TextChoices):
    VACCINE = "vaccine", "Вакцина"
    ANTIBIOTIC = "antibiotic", "Антибиотик"
    VITAMIN = "vitamin", "Витамин"
    ELECTROLYTE = "electrolyte", "Электролит"
    OTHER = "other", "Прочее"


class Route(models.TextChoices):
    INJECTION = "injection", "Инъекция"
    ORAL = "oral", "Оральное"
    DRINKING_WATER = "drinking_water", "С водой"
    SPRAY = "spray", "Спрей"
    OTHER = "other", "Прочее"


class Direction(models.TextChoices):
    BROILER = "broiler", "Бройлер"
    LAYER = "layer", "Несушка"
    PARENT = "parent", "Родительское стадо"


class Indication(models.TextChoices):
    ROUTINE = "routine", "Плановая обработка"
    PROPHYLAXIS = "prophylaxis", "Профилактика"
    THERAPY = "therapy", "Лечение"
    EMERGENCY = "emergency", "Экстренно"


class VetDrug(UUIDModel, TimestampedModel):
    """SKU-карточка ветпрепарата (вет-специфичные характеристики поверх NomenclatureItem)."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="vet_drugs",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="vet_drugs",
    )
    nomenclature = models.ForeignKey(
        "nomenclature.NomenclatureItem",
        on_delete=models.PROTECT,
        related_name="vet_drug_cards",
    )
    drug_type = models.CharField(
        max_length=16, choices=DrugType.choices, db_index=True
    )
    administration_route = models.CharField(max_length=16, choices=Route.choices)
    default_withdrawal_days = models.PositiveSmallIntegerField(default=0)
    storage_conditions = models.CharField(max_length=128, blank=True)
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
        ordering = ["-created_at"]
        unique_together = (("organization", "nomenclature"),)
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["organization", "drug_type"]),
        ]
        verbose_name = "Ветпрепарат"
        verbose_name_plural = "Ветпрепараты"

    def __str__(self):
        return f"{self.nomenclature.sku} · {self.nomenclature.name}"

    def clean(self):
        super().clean()
        if (
            self.nomenclature_id
            and self.organization_id
            and self.nomenclature.organization_id != self.organization_id
        ):
            raise ValidationError(
                {"nomenclature": "Номенклатура из другой организации."}
            )


class VetStockBatch(UUIDModel, TimestampedModel):
    """Партия (lot) препарата на вет-складе."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Доступна"
        QUARANTINE = "quarantine", "На карантине"
        EXPIRING_SOON = "expiring_soon", "Скоро истекает"
        EXPIRED = "expired", "Истекла"
        DEPLETED = "depleted", "Исчерпана"
        RECALLED = "recalled", "Отозвана"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="vet_stock_batches",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="vet_stock_batches",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    drug = models.ForeignKey(
        VetDrug, on_delete=models.PROTECT, related_name="stock_batches"
    )
    lot_number = models.CharField(max_length=64, db_index=True)
    warehouse = models.ForeignKey(
        "warehouses.Warehouse",
        on_delete=models.PROTECT,
        related_name="vet_stock_batches",
    )
    supplier = models.ForeignKey(
        "counterparties.Counterparty",
        on_delete=models.PROTECT,
        related_name="vet_stock_batches",
    )
    purchase = models.ForeignKey(
        "purchases.PurchaseOrder",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vet_stock_batches",
    )
    received_date = models.DateField(db_index=True)
    expiration_date = models.DateField(db_index=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    current_quantity = models.DecimalField(max_digits=12, decimal_places=3)
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
    barcode = models.CharField(
        max_length=64, null=True, blank=True, db_index=True,
        help_text="Уникальный штрих-код лота для розничной продажи и сканирования.",
    )
    recalled_at = models.DateTimeField(null=True, blank=True)
    recall_reason = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    # Порог "скоро истекает" в днях — используется в auto_status сервисе и computed
    EXPIRING_THRESHOLD_DAYS = 30

    class Meta:
        ordering = ["-received_date", "doc_number"]
        unique_together = (
            ("organization", "doc_number"),
            ("organization", "barcode"),
        )
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["drug", "status"]),
            models.Index(fields=["organization", "-received_date"]),
            models.Index(fields=["warehouse", "status"]),
            models.Index(fields=["status", "expiration_date"]),
            models.Index(fields=["organization", "barcode"]),
        ]
        verbose_name = "Партия ветпрепарата"
        verbose_name_plural = "Партии ветпрепаратов"

    def __str__(self):
        return f"{self.doc_number} · {self.drug}"

    @property
    def days_to_expiry(self) -> int | None:
        if not self.expiration_date:
            return None
        return (self.expiration_date - date.today()).days

    @property
    def is_expired(self) -> bool:
        d = self.days_to_expiry
        return d is not None and d < 0

    @property
    def is_expiring_soon(self) -> bool:
        d = self.days_to_expiry
        return d is not None and 0 <= d <= self.EXPIRING_THRESHOLD_DAYS

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return
        if self.drug_id and self.drug.organization_id != org_id:
            raise ValidationError({"drug": "Препарат из другой организации."})
        if self.supplier_id and self.supplier.organization_id != org_id:
            raise ValidationError({"supplier": "Поставщик из другой организации."})
        if self.purchase_id and self.purchase.organization_id != org_id:
            raise ValidationError({"purchase": "Закуп из другой организации."})
        if self.warehouse_id:
            if self.warehouse.organization_id != org_id:
                raise ValidationError({"warehouse": "Склад из другой организации."})
            if self.module_id and self.warehouse.module_id != self.module_id:
                raise ValidationError(
                    {"warehouse": "Склад не принадлежит модулю ветеринарии."}
                )
        if (
            self.quantity is not None
            and self.current_quantity is not None
            and self.current_quantity > self.quantity
        ):
            raise ValidationError(
                {"current_quantity": "Остаток не может превышать начальное количество."}
            )
        if (
            self.received_date is not None
            and self.expiration_date is not None
            and self.expiration_date < self.received_date
        ):
            raise ValidationError(
                {"expiration_date": "Срок годности не может быть раньше даты прихода."}
            )


class VaccinationSchedule(UUIDModel, TimestampedModel):
    """Шаблон схемы вакцинации по направлению (broiler/layer/parent)."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="vaccination_schedules",
    )
    code = models.CharField(max_length=32, db_index=True)
    name = models.CharField(max_length=128)
    direction = models.CharField(
        max_length=16, choices=Direction.choices, db_index=True
    )
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
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
        verbose_name = "Схема вакцинации"
        verbose_name_plural = "Схемы вакцинации"

    def __str__(self):
        return f"{self.code} · {self.name}"


class VaccinationScheduleItem(UUIDModel, TimestampedModel):
    schedule = models.ForeignKey(
        VaccinationSchedule,
        on_delete=models.CASCADE,
        related_name="items",
    )
    day_of_age = models.PositiveSmallIntegerField()
    drug = models.ForeignKey(
        VetDrug, on_delete=models.PROTECT, related_name="schedule_items"
    )
    dose_per_head = models.DecimalField(max_digits=10, decimal_places=4)
    administration_route = models.CharField(
        max_length=16, choices=Route.choices, null=True, blank=True
    )
    is_mandatory = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["schedule", "day_of_age"]
        unique_together = (("schedule", "day_of_age", "drug"),)
        indexes = [models.Index(fields=["schedule", "day_of_age"])]
        verbose_name = "Строка схемы вакцинации"
        verbose_name_plural = "Строки схемы вакцинации"

    def __str__(self):
        return f"{self.schedule.code} · день {self.day_of_age} · {self.drug}"

    def clean(self):
        super().clean()
        if (
            self.drug_id
            and self.schedule_id
            and self.drug.organization_id != self.schedule.organization_id
        ):
            raise ValidationError({"drug": "Препарат из другой организации."})
        if self.dose_per_head is not None and self.dose_per_head <= 0:
            raise ValidationError({"dose_per_head": "Доза должна быть больше нуля."})


class VetTreatmentLog(UUIDModel, TimestampedModel):
    """Фактическая запись применения препарата."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="vet_treatment_logs",
    )
    module = models.ForeignKey(
        "modules.Module",
        on_delete=models.PROTECT,
        related_name="vet_treatment_logs",
    )
    doc_number = models.CharField(max_length=32, db_index=True)
    treatment_date = models.DateField(db_index=True)

    target_block = models.ForeignKey(
        "warehouses.ProductionBlock",
        on_delete=models.PROTECT,
        related_name="vet_treatments",
    )
    target_batch = models.ForeignKey(
        "batches.Batch",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vet_treatments",
    )
    target_herd = models.ForeignKey(
        "matochnik.BreedingHerd",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="vet_treatments",
    )

    drug = models.ForeignKey(
        VetDrug, on_delete=models.PROTECT, related_name="treatment_logs"
    )
    stock_batch = models.ForeignKey(
        VetStockBatch,
        on_delete=models.PROTECT,
        related_name="consumed_in_treatments",
    )
    dose_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit = models.ForeignKey(
        "nomenclature.Unit",
        on_delete=models.PROTECT,
        related_name="+",
    )
    heads_treated = models.PositiveIntegerField()
    withdrawal_period_days = models.PositiveSmallIntegerField(default=0)
    administration_route = models.CharField(
        max_length=16, choices=Route.choices, null=True, blank=True
    )

    veterinarian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="vet_treatments_supervised",
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    schedule_item = models.ForeignKey(
        VaccinationScheduleItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="treatment_logs",
    )
    indication = models.CharField(
        max_length=16, choices=Indication.choices, db_index=True
    )
    notes = models.TextField(blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=255, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-treatment_date", "doc_number"]
        unique_together = (("organization", "doc_number"),)
        indexes = [
            models.Index(fields=["organization", "-treatment_date"]),
            models.Index(fields=["target_batch", "-treatment_date"]),
            models.Index(fields=["target_herd", "-treatment_date"]),
            models.Index(fields=["drug", "-treatment_date"]),
            models.Index(fields=["stock_batch"]),
            models.Index(fields=["organization", "indication"]),
        ]
        verbose_name = "Журнал применения"
        verbose_name_plural = "Журнал применений"

    def __str__(self):
        target = self.target_batch or self.target_herd
        return f"{self.doc_number} · {self.drug} · {target}"

    def clean(self):
        super().clean()
        org_id = self.organization_id
        if not org_id:
            return

        # XOR target: ровно один из двух
        has_batch = bool(self.target_batch_id)
        has_herd = bool(self.target_herd_id)
        if has_batch and has_herd:
            raise ValidationError(
                "Должен быть указан ровно один из: партия (target_batch) или "
                "родительское стадо (target_herd), не оба."
            )
        if not has_batch and not has_herd:
            raise ValidationError(
                "Необходимо указать партию (target_batch) или родительское стадо (target_herd)."
            )

        # cross-org validators.
        # Замечание: target_block принадлежит ЦЕЛЕВОМУ модулю (feedlot/matochnik/...),
        # не модулю ветаптеки, поэтому проверяем только org-совпадение.
        if self.target_block_id and self.target_block.organization_id != org_id:
            raise ValidationError({"target_block": "Блок из другой организации."})
        if self.target_batch_id and self.target_batch.organization_id != org_id:
            raise ValidationError({"target_batch": "Партия из другой организации."})
        if self.target_herd_id and self.target_herd.organization_id != org_id:
            raise ValidationError({"target_herd": "Стадо из другой организации."})
        if self.drug_id and self.drug.organization_id != org_id:
            raise ValidationError({"drug": "Препарат из другой организации."})
        if self.stock_batch_id and self.stock_batch.organization_id != org_id:
            raise ValidationError(
                {"stock_batch": "Лот препарата из другой организации."}
            )

        # stock_batch.drug == drug
        if (
            self.stock_batch_id
            and self.drug_id
            and self.stock_batch.drug_id != self.drug_id
        ):
            raise ValidationError(
                {"stock_batch": "Лот принадлежит другому препарату."}
            )

        # soft-check наличия: лот должен покрывать дозу (сервис Phase 7 делает atomic декремент)
        if (
            self.stock_batch_id
            and self.dose_quantity is not None
            and self.stock_batch.current_quantity is not None
            and self.dose_quantity > self.stock_batch.current_quantity
        ):
            raise ValidationError(
                {"dose_quantity": "Остаток лота меньше необходимой дозы."}
            )

        if self.dose_quantity is not None and self.dose_quantity <= 0:
            raise ValidationError({"dose_quantity": "Доза должна быть больше нуля."})
        if self.heads_treated is not None and self.heads_treated <= 0:
            raise ValidationError(
                {"heads_treated": "Количество голов должно быть больше нуля."}
            )

        # schedule_item consistency
        if self.schedule_item_id and self.drug_id:
            if self.schedule_item.drug_id != self.drug_id:
                raise ValidationError(
                    {"schedule_item": "Строка шаблона относится к другому препарату."}
                )
            if self.schedule_item.schedule.organization_id != org_id:
                raise ValidationError(
                    {"schedule_item": "Шаблон из другой организации."}
                )


class SellerDeviceToken(UUIDModel, TimestampedModel):
    """
    Долговременный токен продавца для public-сканера/розничных продаж.

    Используется на public-страницах /scan/<barcode> + /api/vet/public/sell/.
    Аутентификация через `apps.vet.authentication.SellerTokenAuthentication`.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="seller_tokens",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.PROTECT,
        related_name="seller_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    label = models.CharField(
        max_length=64, blank=True,
        help_text="Описание устройства/точки продаж, например «Магазин Юнусабад».",
    )
    is_active = models.BooleanField(default=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "is_active"]),
            models.Index(fields=["user", "is_active"]),
        ]
        verbose_name = "Токен продавца"
        verbose_name_plural = "Токены продавцов"

    def __str__(self):
        return f"{self.user} · {self.label or 'без метки'}"

    @property
    def masked_token(self) -> str:
        if not self.token:
            return ""
        return "****" + self.token[-4:]
