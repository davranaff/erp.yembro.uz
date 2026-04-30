from rest_framework import serializers

from apps.common.serializers import FinancialFieldsMixin

from .models import (
    SellerDeviceToken,
    VaccinationSchedule,
    VaccinationScheduleItem,
    VetDrug,
    VetStockBatch,
    VetTreatmentLog,
)


class VetDrugSerializer(serializers.ModelSerializer):
    nomenclature_sku = serializers.SerializerMethodField()
    nomenclature_name = serializers.SerializerMethodField()

    class Meta:
        model = VetDrug
        fields = (
            "id",
            "module",
            "nomenclature",
            "drug_type",
            "administration_route",
            "default_withdrawal_days",
            "storage_conditions",
            "is_active",
            "notes",
            "nomenclature_sku",
            "nomenclature_name",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "nomenclature_sku",
            "nomenclature_name",
            "created_at",
            "updated_at",
        )

    def get_nomenclature_sku(self, obj):
        return obj.nomenclature.sku if obj.nomenclature_id else None

    def get_nomenclature_name(self, obj):
        return obj.nomenclature.name if obj.nomenclature_id else None


class VetStockBatchSerializer(FinancialFieldsMixin, serializers.ModelSerializer):
    # Закупочные цены вет-препаратов — деньги модуля vet
    financial_fields = ("price_per_unit_uzs",)
    finances_module = "vet"

    drug_sku = serializers.SerializerMethodField()
    drug_name = serializers.SerializerMethodField()
    drug_type = serializers.SerializerMethodField()
    warehouse_code = serializers.SerializerMethodField()
    supplier_name = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    days_to_expiry = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)

    class Meta:
        model = VetStockBatch
        fields = (
            "id",
            "doc_number",
            "module",
            "drug",
            "lot_number",
            "warehouse",
            "supplier",
            "purchase",
            "received_date",
            "expiration_date",
            "quantity",
            "current_quantity",
            "unit",
            "price_per_unit_uzs",
            "status",
            "quarantine_until",
            "barcode",
            "recalled_at",
            "recall_reason",
            "notes",
            "drug_sku",
            "drug_name",
            "drug_type",
            "warehouse_code",
            "supplier_name",
            "unit_code",
            "days_to_expiry",
            "is_expired",
            "is_expiring_soon",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "barcode",
            "recalled_at",
            "recall_reason",
            "drug_sku",
            "drug_name",
            "drug_type",
            "warehouse_code",
            "supplier_name",
            "unit_code",
            "days_to_expiry",
            "is_expired",
            "is_expiring_soon",
            "created_at",
            "updated_at",
        )

    def get_drug_type(self, obj):
        return obj.drug.drug_type if obj.drug_id else None

    def get_drug_sku(self, obj):
        if not obj.drug_id:
            return None
        return obj.drug.nomenclature.sku if obj.drug.nomenclature_id else None

    def get_drug_name(self, obj):
        if not obj.drug_id:
            return None
        return obj.drug.nomenclature.name if obj.drug.nomenclature_id else None

    def get_warehouse_code(self, obj):
        return obj.warehouse.code if obj.warehouse_id else None

    def get_supplier_name(self, obj):
        return obj.supplier.name if obj.supplier_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None


class VaccinationScheduleItemSerializer(serializers.ModelSerializer):
    drug_sku = serializers.SerializerMethodField()

    class Meta:
        model = VaccinationScheduleItem
        fields = (
            "id",
            "schedule",
            "day_of_age",
            "drug",
            "dose_per_head",
            "administration_route",
            "is_mandatory",
            "notes",
            "drug_sku",
        )
        read_only_fields = ("id", "drug_sku")

    def get_drug_sku(self, obj):
        if not obj.drug_id:
            return None
        return obj.drug.nomenclature.sku if obj.drug.nomenclature_id else None


class VaccinationScheduleSerializer(serializers.ModelSerializer):
    items = VaccinationScheduleItemSerializer(many=True, read_only=True)

    class Meta:
        model = VaccinationSchedule
        fields = (
            "id",
            "code",
            "name",
            "direction",
            "description",
            "is_active",
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "items", "created_at", "updated_at")


class VetTreatmentLogSerializer(serializers.ModelSerializer):
    drug_sku = serializers.SerializerMethodField()
    stock_batch_lot = serializers.SerializerMethodField()
    target_batch_doc = serializers.SerializerMethodField()
    target_herd_doc = serializers.SerializerMethodField()
    target_block_code = serializers.SerializerMethodField()

    class Meta:
        model = VetTreatmentLog
        fields = (
            "id",
            "doc_number",
            "module",
            "treatment_date",
            "target_block",
            "target_batch",
            "target_herd",
            "drug",
            "stock_batch",
            "dose_quantity",
            "unit",
            "heads_treated",
            "withdrawal_period_days",
            "administration_route",
            "veterinarian",
            "technician",
            "schedule_item",
            "indication",
            "notes",
            "cancelled_at",
            "cancel_reason",
            "cancelled_by",
            "drug_sku",
            "stock_batch_lot",
            "target_batch_doc",
            "target_herd_doc",
            "target_block_code",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "cancelled_at",
            "cancel_reason",
            "cancelled_by",
            "drug_sku",
            "stock_batch_lot",
            "target_batch_doc",
            "target_herd_doc",
            "target_block_code",
            "created_at",
            "updated_at",
        )

    def get_drug_sku(self, obj):
        if not obj.drug_id:
            return None
        return obj.drug.nomenclature.sku if obj.drug.nomenclature_id else None

    def get_stock_batch_lot(self, obj):
        return obj.stock_batch.lot_number if obj.stock_batch_id else None

    def get_target_batch_doc(self, obj):
        return obj.target_batch.doc_number if obj.target_batch_id else None

    def get_target_herd_doc(self, obj):
        return obj.target_herd.doc_number if obj.target_herd_id else None

    def get_target_block_code(self, obj):
        return obj.target_block.code if obj.target_block_id else None


class VetStockBatchPublicSerializer(serializers.ModelSerializer):
    """Сериализатор для public-эндпоинта /api/vet/public/scan/<barcode>/.

    Без чувствительных данных: organization, supplier, purchase, warehouse, notes.
    """
    drug_sku = serializers.SerializerMethodField()
    drug_name = serializers.SerializerMethodField()
    drug_type = serializers.SerializerMethodField()
    drug_type_display = serializers.SerializerMethodField()
    unit_code = serializers.SerializerMethodField()
    days_to_expiry = serializers.IntegerField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    is_expiring_soon = serializers.BooleanField(read_only=True)

    class Meta:
        model = VetStockBatch
        fields = (
            "id",
            "barcode",
            "drug_sku",
            "drug_name",
            "drug_type",
            "drug_type_display",
            "lot_number",
            "expiration_date",
            "current_quantity",
            "unit_code",
            "price_per_unit_uzs",
            "status",
            "days_to_expiry",
            "is_expired",
            "is_expiring_soon",
        )

    def get_drug_sku(self, obj):
        return obj.drug.nomenclature.sku if obj.drug_id else None

    def get_drug_name(self, obj):
        return obj.drug.nomenclature.name if obj.drug_id else None

    def get_drug_type(self, obj):
        return obj.drug.drug_type if obj.drug_id else None

    def get_drug_type_display(self, obj):
        return obj.drug.get_drug_type_display() if obj.drug_id else None

    def get_unit_code(self, obj):
        return obj.unit.code if obj.unit_id else None


class SellerDeviceTokenSerializer(serializers.ModelSerializer):
    """Список/чтение токенов — `token` НЕ показываем (только masked)."""
    user_full_name = serializers.SerializerMethodField()
    user_email = serializers.SerializerMethodField()
    masked_token = serializers.CharField(read_only=True)

    class Meta:
        model = SellerDeviceToken
        fields = (
            "id",
            "user",
            "user_full_name",
            "user_email",
            "label",
            "is_active",
            "masked_token",
            "last_used_at",
            "revoked_at",
            "created_at",
        )
        read_only_fields = fields

    def get_user_full_name(self, obj):
        return getattr(obj.user, "full_name", None) or str(obj.user)

    def get_user_email(self, obj):
        return getattr(obj.user, "email", None)


class SellerDeviceTokenCreateSerializer(serializers.ModelSerializer):
    """При создании возвращаем `token` в plain виде (один раз)."""

    class Meta:
        model = SellerDeviceToken
        fields = (
            "id",
            "user",
            "label",
            "token",
            "is_active",
            "created_at",
        )
        read_only_fields = ("id", "token", "is_active", "created_at")
